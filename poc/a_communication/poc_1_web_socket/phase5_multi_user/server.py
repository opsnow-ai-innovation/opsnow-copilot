"""
Phase 5: 멀티 유저 PoC

검증 항목:
- 동일 사용자 다중 연결 정책 (옵션)
- Rate Limit 공유 정책 (옵션)
- 동시 요청 독립 처리
- 연결 현황 실시간 추적
"""

import asyncio
import json
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 상위 디렉토리의 auth 모듈 import
sys.path.append(str(Path(__file__).parent.parent / "phase2_auth"))
from auth import generate_token, validate_token, get_user_info, JWT_EXPIRY_SECONDS

# =============================================================================
# 설정 (옵션)
# =============================================================================

# 동일 사용자 다중 연결 정책
SINGLE_SESSION_PER_USER = False     # True: 새 연결 시 기존 연결 끊김
                                    # False: 여러 연결 동시 허용

# Rate Limit 공유 정책
SHARE_RATE_LIMIT = True             # True: 모든 연결이 10회 공유
                                    # False: 각 연결마다 10회 별도

HEARTBEAT_INTERVAL = 30
PONG_TIMEOUT = 10
MAX_MISSED_PONGS = 3
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60


# =============================================================================
# Connection Manager
# =============================================================================

@dataclass
class ConnectionInfo:
    """연결 정보"""
    websocket: WebSocket
    username: str
    connection_id: str
    connected_at: datetime
    user_info: dict


class ConnectionManager:
    """다중 사용자 연결 관리"""

    def __init__(self):
        # username -> [ConnectionInfo, ...]
        self._connections: dict[str, list[ConnectionInfo]] = defaultdict(list)
        self._connection_by_id: dict[str, ConnectionInfo] = {}

    def get_user_connections(self, username: str) -> list[ConnectionInfo]:
        """사용자의 모든 연결 조회"""
        return self._connections.get(username, [])

    def get_connection_count(self, username: str) -> int:
        """사용자의 연결 수"""
        return len(self._connections.get(username, []))

    def add(self, conn_info: ConnectionInfo) -> ConnectionInfo | None:
        """
        연결 추가

        Returns:
            기존 연결 (SINGLE_SESSION_PER_USER=True일 때 끊을 연결)
        """
        username = conn_info.username
        old_connection = None

        if SINGLE_SESSION_PER_USER:
            # 단일 세션만 허용 - 기존 연결이 있으면 반환 (호출자가 끊어야 함)
            existing = self._connections.get(username, [])
            if existing:
                old_connection = existing[0]
                self._connections[username] = []
                del self._connection_by_id[old_connection.connection_id]

        self._connections[username].append(conn_info)
        self._connection_by_id[conn_info.connection_id] = conn_info

        return old_connection

    def remove(self, connection_id: str) -> bool:
        """연결 제거"""
        if connection_id not in self._connection_by_id:
            return False

        conn_info = self._connection_by_id.pop(connection_id)
        username = conn_info.username

        self._connections[username] = [
            c for c in self._connections[username]
            if c.connection_id != connection_id
        ]

        if not self._connections[username]:
            del self._connections[username]

        return True

    def get_all_connections(self) -> list[dict]:
        """모든 연결 현황"""
        result = []
        for username, connections in self._connections.items():
            for conn in connections:
                result.append({
                    "username": username,
                    "connectionId": conn.connection_id,
                    "connectedAt": conn.connected_at.isoformat(),
                    "name": conn.user_info.get("name", "")
                })
        return result

    def get_stats(self) -> dict:
        """연결 통계"""
        total_connections = sum(len(conns) for conns in self._connections.values())
        return {
            "totalUsers": len(self._connections),
            "totalConnections": total_connections,
            "users": {
                username: len(conns)
                for username, conns in self._connections.items()
            }
        }


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Rate Limiter (사용자 기준 또는 연결 기준)"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_key(self, username: str, connection_id: str) -> str:
        """Rate Limit 키 결정"""
        if SHARE_RATE_LIMIT:
            return username
        else:
            return connection_id

    def is_allowed(self, username: str, connection_id: str) -> tuple[bool, dict]:
        """요청 허용 여부 확인"""
        key = self._get_key(username, connection_id)
        now = time.time()
        window_start = now - self.window_seconds

        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        current_count = len(self._requests[key])
        remaining = max(0, self.max_requests - current_count)

        info = {
            "limit": self.max_requests,
            "remaining": remaining,
            "reset": int(window_start + self.window_seconds),
            "window": self.window_seconds,
            "limitKey": "user" if SHARE_RATE_LIMIT else "connection"
        }

        if current_count >= self.max_requests:
            if self._requests[key]:
                oldest = min(self._requests[key])
                info["retry_after"] = int(oldest + self.window_seconds - now) + 1
            return False, info

        self._requests[key].append(now)
        info["remaining"] = remaining - 1

        return True, info

    def get_status(self, username: str, connection_id: str) -> dict:
        """현재 Rate Limit 상태 조회"""
        key = self._get_key(username, connection_id)
        now = time.time()
        window_start = now - self.window_seconds

        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        current_count = len(self._requests[key])
        return {
            "limit": self.max_requests,
            "used": current_count,
            "remaining": max(0, self.max_requests - current_count),
            "window": self.window_seconds,
            "limitKey": "user" if SHARE_RATE_LIMIT else "connection"
        }

    def reset(self, username: str, connection_id: str):
        """Rate Limit 초기화"""
        key = self._get_key(username, connection_id)
        self._requests[key] = []


# =============================================================================
# 전역 인스턴스
# =============================================================================

connection_manager = ConnectionManager()
rate_limiter = RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server started - Multi User Mode")
    print(f"SINGLE_SESSION_PER_USER: {SINGLE_SESSION_PER_USER} ({'단일 연결만' if SINGLE_SESSION_PER_USER else '다중 연결 허용'})")
    print(f"SHARE_RATE_LIMIT: {SHARE_RATE_LIMIT} ({'공유' if SHARE_RATE_LIMIT else '별도'})")
    yield
    print("Server stopped")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REST API
# =============================================================================

@app.post("/api/auth/token")
async def create_token(
    username: str = "test@example.com",
    name: str = "테스트 사용자"
):
    token = generate_token(username=username, name=name)
    return {"access_token": token, "token_type": "Bearer", "expires_in": JWT_EXPIRY_SECONDS}


@app.get("/api/connections")
async def get_connections():
    """현재 연결 현황 조회"""
    return {
        "stats": connection_manager.get_stats(),
        "connections": connection_manager.get_all_connections(),
        "settings": {
            "singleSessionPerUser": SINGLE_SESSION_PER_USER,
            "shareRateLimit": SHARE_RATE_LIMIT
        }
    }


@app.post("/api/rate-limit/reset")
async def reset_rate_limit(username: str, connection_id: str = ""):
    """Rate Limit 초기화"""
    rate_limiter.reset(username, connection_id)
    return {"message": f"Rate limit reset for {username}"}


# =============================================================================
# Heartbeat Manager
# =============================================================================

class HeartbeatManager:
    """Ping/Pong 기반 연결 상태 관리"""

    def __init__(self, websocket: WebSocket, username: str, connection_id: str):
        self.websocket = websocket
        self.username = username
        self.connection_id = connection_id
        self.pong_received = asyncio.Event()
        self.missed_pongs = 0
        self.should_disconnect = False

    async def heartbeat_loop(self):
        """Heartbeat 루프"""
        try:
            while not self.should_disconnect:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                if self.should_disconnect:
                    break

                self.pong_received.clear()
                await self.websocket.send_json({
                    "type": "ping",
                    "missedPongs": self.missed_pongs,
                    "maxMissedPongs": MAX_MISSED_PONGS
                })

                try:
                    await asyncio.wait_for(
                        self.pong_received.wait(),
                        timeout=PONG_TIMEOUT
                    )
                    self.missed_pongs = 0

                except asyncio.TimeoutError:
                    self.missed_pongs += 1
                    print(f"  [Heartbeat] [{self.username}:{self.connection_id[:8]}] pong 타임아웃 ({self.missed_pongs}/{MAX_MISSED_PONGS})")

                    if self.missed_pongs >= MAX_MISSED_PONGS:
                        self.should_disconnect = True
                        await self.websocket.close(
                            code=4003,
                            reason=f"Pong timeout ({MAX_MISSED_PONGS} missed)"
                        )
                        break

        except Exception as e:
            print(f"  [Heartbeat] [{self.username}] 에러: {e}")

    def on_pong_received(self):
        """pong 메시지 수신 시 호출"""
        self.pong_received.set()


# =============================================================================
# WebSocket 엔드포인트
# =============================================================================

@app.websocket("/ws/copilot")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None)
):
    timestamp = datetime.now().strftime('%H:%M:%S')
    connection_id = str(uuid.uuid4())

    # 1. JWT 검증
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload, error, _ = validate_token(token)
    if error:
        await websocket.close(code=4001, reason=error)
        return

    user_info = get_user_info(payload)
    username = user_info["username"]

    # 2. 연결 정보 생성
    conn_info = ConnectionInfo(
        websocket=websocket,
        username=username,
        connection_id=connection_id,
        connected_at=datetime.now(),
        user_info=user_info
    )

    # 3. 연결 관리자에 추가 (다중 연결 정책 적용)
    old_connection = connection_manager.add(conn_info)

    # 기존 연결 끊기 (SINGLE_SESSION_PER_USER=True일 때)
    if old_connection:
        try:
            await old_connection.websocket.close(
                code=4002,
                reason="New connection from same user"
            )
            print(f"[{timestamp}] 기존 연결 종료: {username} ({old_connection.connection_id[:8]})")
        except:
            pass

    conn_count = connection_manager.get_connection_count(username)
    print(f"[{timestamp}] 연결 성공: {username} (connId: {connection_id[:8]}, 총 {conn_count}개)")

    # 4. 연결 수락
    await websocket.accept()

    # 5. connected 메시지
    rate_status = rate_limiter.get_status(username, connection_id)
    await websocket.send_json({
        "type": "connected",
        "serverTime": datetime.now().isoformat(),
        "user": user_info,
        "connectionId": connection_id,
        "connectionCount": conn_count,
        "rateLimit": rate_status,
        "settings": {
            "singleSessionPerUser": SINGLE_SESSION_PER_USER,
            "shareRateLimit": SHARE_RATE_LIMIT
        }
    })

    # 6. 하트비트 매니저
    heartbeat_manager = HeartbeatManager(websocket, username, connection_id)
    heartbeat_task = asyncio.create_task(heartbeat_manager.heartbeat_loop())

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}:{connection_id[:8]}] 수신: {msg_type}")

            if msg_type == "pong":
                heartbeat_manager.on_pong_received()
                continue

            if msg_type == "get_rate_limit":
                status_info = rate_limiter.get_status(username, connection_id)
                await websocket.send_json({
                    "type": "rate_limit_status",
                    "rateLimit": status_info
                })
                continue

            if msg_type == "query":
                allowed, rate_info = rate_limiter.is_allowed(username, connection_id)

                if not allowed:
                    print(f"  -> Rate Limit 초과!")
                    await websocket.send_json({
                        "type": "error",
                        "code": "RATE_LIMITED",
                        "message": f"요청 한도 초과. {rate_info.get('retry_after', 60)}초 후 재시도하세요.",
                        "rateLimit": rate_info
                    })
                    continue

                query = data.get("query", "")
                print(f"  - 질문: {query} (remaining: {rate_info['remaining']})")

                # 간단한 응답 (처리 시간 시뮬레이션)
                await asyncio.sleep(0.5)

                await websocket.send_json({
                    "type": "response",
                    "answer": f"**[{username}]** 님의 질문에 대한 응답\n\n> {query}\n\n처리 완료 (connId: {connection_id[:8]})",
                    "rateLimit": rate_info,
                    "connectionId": connection_id
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": f"알 수 없는 메시지 타입: {msg_type}"
                })

    except WebSocketDisconnect:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}:{connection_id[:8]}] 연결 종료")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 에러: {e}")
    finally:
        heartbeat_manager.should_disconnect = True
        heartbeat_task.cancel()
        connection_manager.remove(connection_id)
        remaining = connection_manager.get_connection_count(username)
        print(f"  -> {username} 남은 연결: {remaining}개")


@app.get("/")
async def get_test_page():
    return HTMLResponse(content="""
    <html>
    <head><title>WebSocket PoC - Phase 5 (Multi User)</title></head>
    <body>
        <h1>WebSocket 멀티 유저 테스트</h1>
        <h2>검증 항목</h2>
        <ul>
            <li>동일 사용자 다중 연결 정책</li>
            <li>Rate Limit 공유 정책</li>
            <li>동시 요청 독립 처리</li>
            <li>연결 현황 실시간 추적</li>
        </ul>
        <p>client.html 파일을 브라우저에서 열어 테스트하세요.</p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
