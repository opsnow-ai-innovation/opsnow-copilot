"""
Phase 4: 안정성 PoC (재연결, Rate Limiting, Pong 타임아웃)

검증 항목:
- Rate Limiting (10 req/60s)
- 429 Too Many Requests 처리
- 에러 메시지 (TIMEOUT, INVALID_MESSAGE, RATE_LIMITED)
- 서버 강제 종료 시뮬레이션 (재연결 테스트용)
- Pong 타임아웃 → 연결 끊기 (3회 무응답 시)
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 상위 디렉토리의 auth 모듈 import
sys.path.append(str(Path(__file__).parent.parent / "phase2_auth"))
from auth import generate_token, validate_token, get_user_info, JWT_EXPIRY_SECONDS

# 설정
HEARTBEAT_INTERVAL = 30  # ping 전송 간격 (초)
PONG_TIMEOUT = 10  # pong 응답 대기 시간 (초)
MAX_MISSED_PONGS = 3  # 최대 허용 무응답 횟수
RATE_LIMIT_MAX_REQUESTS = 10  # 최대 요청 수
RATE_LIMIT_WINDOW_SECONDS = 60  # 시간 윈도우 (초)


class RateLimiter:
    """사용자별 Rate Limiter"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> tuple[bool, dict]:
        """
        요청 허용 여부 확인

        Returns:
            (allowed, info) - allowed: 허용 여부, info: 상태 정보
        """
        now = time.time()
        window_start = now - self.window_seconds

        # 윈도우 밖의 오래된 요청 제거
        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if ts > window_start
        ]

        current_count = len(self._requests[user_id])
        remaining = max(0, self.max_requests - current_count)

        info = {
            "limit": self.max_requests,
            "remaining": remaining,
            "reset": int(window_start + self.window_seconds),
            "window": self.window_seconds
        }

        if current_count >= self.max_requests:
            # 가장 오래된 요청이 만료되는 시간
            if self._requests[user_id]:
                oldest = min(self._requests[user_id])
                info["retry_after"] = int(oldest + self.window_seconds - now) + 1
            return False, info

        # 요청 기록
        self._requests[user_id].append(now)
        info["remaining"] = remaining - 1

        return True, info

    def get_status(self, user_id: str) -> dict:
        """현재 Rate Limit 상태 조회"""
        now = time.time()
        window_start = now - self.window_seconds

        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if ts > window_start
        ]

        current_count = len(self._requests[user_id])
        return {
            "limit": self.max_requests,
            "used": current_count,
            "remaining": max(0, self.max_requests - current_count),
            "window": self.window_seconds
        }


# 전역 Rate Limiter
rate_limiter = RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)

# 연결 관리 (빠른 테스트용)
active_heartbeat_managers: dict[str, "HeartbeatManager"] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server started - Stability Test Mode")
    print(f"Rate Limit: {RATE_LIMIT_MAX_REQUESTS} requests / {RATE_LIMIT_WINDOW_SECONDS} seconds")
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


@app.get("/api/rate-limit/status")
async def get_rate_limit_status(user_id: str = "test"):
    """Rate Limit 상태 조회 (테스트용)"""
    return rate_limiter.get_status(user_id)


@app.post("/api/rate-limit/reset")
async def reset_rate_limit(user_id: str = "test"):
    """Rate Limit 초기화 (테스트용)"""
    rate_limiter._requests[user_id] = []
    return {"message": f"Rate limit reset for {user_id}"}


@app.post("/api/heartbeat/quick-test")
async def enable_quick_heartbeat_test(token: str = Query(default=None)):
    """빠른 Heartbeat 테스트 활성화 (테스트용)"""
    if not token:
        return JSONResponse(status_code=400, content={"error": "Token required"})

    payload, error, _ = validate_token(token)
    if error:
        return JSONResponse(status_code=401, content={"error": error})

    username = payload.get("preferred_username", "unknown")

    if username in active_heartbeat_managers:
        manager = active_heartbeat_managers[username]
        manager.enable_quick_test()
        return {
            "message": f"Quick test enabled for {username}",
            "interval": HeartbeatManager.QUICK_TEST_INTERVAL,
            "pongTimeout": HeartbeatManager.QUICK_TEST_PONG_TIMEOUT,
            "maxMissedPongs": MAX_MISSED_PONGS
        }
    else:
        return JSONResponse(
            status_code=404,
            content={"error": f"No active connection for {username}"}
        )


@app.post("/api/heartbeat/normal")
async def disable_quick_heartbeat_test(token: str = Query(default=None)):
    """정상 Heartbeat 모드 복원 (테스트용)"""
    if not token:
        return JSONResponse(status_code=400, content={"error": "Token required"})

    payload, error, _ = validate_token(token)
    if error:
        return JSONResponse(status_code=401, content={"error": error})

    username = payload.get("preferred_username", "unknown")

    if username in active_heartbeat_managers:
        manager = active_heartbeat_managers[username]
        manager.disable_quick_test()
        return {
            "message": f"Normal mode restored for {username}",
            "interval": HEARTBEAT_INTERVAL,
            "pongTimeout": PONG_TIMEOUT,
            "maxMissedPongs": MAX_MISSED_PONGS
        }
    else:
        return JSONResponse(
            status_code=404,
            content={"error": f"No active connection for {username}"}
        )


# =============================================================================
# WebSocket 엔드포인트
# =============================================================================

class HeartbeatManager:
    """Ping/Pong 기반 연결 상태 관리"""

    # 빠른 테스트 설정
    QUICK_TEST_INTERVAL = 5  # 5초 간격
    QUICK_TEST_PONG_TIMEOUT = 3  # 3초 대기

    def __init__(self, websocket: WebSocket, username: str):
        self.websocket = websocket
        self.username = username
        self.pong_received = asyncio.Event()
        self.missed_pongs = 0
        self.should_disconnect = False
        self.quick_test_mode = False

    async def heartbeat_loop(self):
        """Heartbeat 루프 - ping 전송 및 pong 대기"""
        try:
            while not self.should_disconnect:
                # 빠른 테스트 모드면 짧은 간격 사용
                interval = self.QUICK_TEST_INTERVAL if self.quick_test_mode else HEARTBEAT_INTERVAL
                pong_timeout = self.QUICK_TEST_PONG_TIMEOUT if self.quick_test_mode else PONG_TIMEOUT

                await asyncio.sleep(interval)

                if self.should_disconnect:
                    break

                # ping 전송
                self.pong_received.clear()
                await self.websocket.send_json({
                    "type": "ping",
                    "missedPongs": self.missed_pongs,
                    "maxMissedPongs": MAX_MISSED_PONGS,
                    "quickTestMode": self.quick_test_mode
                })
                mode_str = " [빠른테스트]" if self.quick_test_mode else ""
                print(f"  [Heartbeat] [{self.username}]{mode_str} ping 전송 (missed: {self.missed_pongs}/{MAX_MISSED_PONGS})")

                # pong 대기
                try:
                    await asyncio.wait_for(
                        self.pong_received.wait(),
                        timeout=pong_timeout
                    )
                    # pong 수신 성공
                    self.missed_pongs = 0
                    print(f"  [Heartbeat] [{self.username}] pong 수신 OK")

                except asyncio.TimeoutError:
                    # pong 타임아웃
                    self.missed_pongs += 1
                    print(f"  [Heartbeat] [{self.username}] pong 타임아웃! ({self.missed_pongs}/{MAX_MISSED_PONGS})")

                    if self.missed_pongs >= MAX_MISSED_PONGS:
                        print(f"  [Heartbeat] [{self.username}] 최대 무응답 초과 - 연결 종료")
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

    def enable_quick_test(self):
        """빠른 테스트 모드 활성화"""
        self.quick_test_mode = True
        self.missed_pongs = 0  # 카운터 리셋
        print(f"  [Heartbeat] [{self.username}] 빠른 테스트 모드 활성화")

    def disable_quick_test(self):
        """빠른 테스트 모드 비활성화 (정상 모드 복원)"""
        self.quick_test_mode = False
        self.missed_pongs = 0  # 카운터 리셋
        print(f"  [Heartbeat] [{self.username}] 정상 모드 복원")


@app.websocket("/ws/copilot")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None)
):
    timestamp = datetime.now().strftime('%H:%M:%S')

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
    rate_limit_key = username  # Rate Limit 키로 username 사용
    print(f"[{timestamp}] 연결 성공: {username}")

    # 2. 연결 수락
    await websocket.accept()

    # 3. connected 메시지 (Rate Limit 정보 포함)
    rate_status = rate_limiter.get_status(rate_limit_key)
    await websocket.send_json({
        "type": "connected",
        "serverTime": datetime.now().isoformat(),
        "user": user_info,
        "rateLimit": rate_status
    })

    # 4. 하트비트 매니저
    heartbeat_manager = HeartbeatManager(websocket, username)
    active_heartbeat_managers[username] = heartbeat_manager  # 전역 등록
    heartbeat_task = asyncio.create_task(heartbeat_manager.heartbeat_loop())

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}] 수신: {msg_type}")

            # pong 처리 - HeartbeatManager에 알림
            if msg_type == "pong":
                heartbeat_manager.on_pong_received()
                continue

            # Rate Limit 상태 조회
            if msg_type == "get_rate_limit":
                status_info = rate_limiter.get_status(rate_limit_key)
                await websocket.send_json({
                    "type": "rate_limit_status",
                    "rateLimit": status_info
                })
                continue

            # Rate Limit 체크 (query만)
            if msg_type == "query":
                allowed, rate_info = rate_limiter.is_allowed(rate_limit_key)

                if not allowed:
                    print(f"  -> Rate Limit 초과! (retry_after: {rate_info.get('retry_after')}s)")
                    await websocket.send_json({
                        "type": "error",
                        "code": "RATE_LIMITED",
                        "message": f"요청 한도 초과. {rate_info.get('retry_after', 60)}초 후 재시도하세요.",
                        "rateLimit": rate_info
                    })
                    continue

                # 정상 처리
                query = data.get("query", "")
                print(f"  - 질문: {query} (remaining: {rate_info['remaining']})")

                # 간단한 응답 생성
                await websocket.send_json({
                    "type": "response",
                    "answer": f"**응답**\n\n질문: {query}\n\n처리 완료.",
                    "rateLimit": rate_info
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": f"알 수 없는 메시지 타입: {msg_type}"
                })

    except WebSocketDisconnect:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}] 연결 종료")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 에러: {e}")
    finally:
        heartbeat_manager.should_disconnect = True
        heartbeat_task.cancel()
        active_heartbeat_managers.pop(username, None)  # 전역에서 제거


@app.get("/")
async def get_test_page():
    return HTMLResponse(content="""
    <html>
    <head><title>WebSocket PoC - Phase 4 (Stability)</title></head>
    <body>
        <h1>WebSocket 안정성 테스트</h1>
        <h2>검증 항목</h2>
        <ul>
            <li>Rate Limiting (10 req/60s)</li>
            <li>429 Too Many Requests 처리</li>
            <li>Exponential Backoff 재연결</li>
            <li>메시지 큐잉</li>
        </ul>
        <p>client.html 파일을 브라우저에서 열어 테스트하세요.</p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
