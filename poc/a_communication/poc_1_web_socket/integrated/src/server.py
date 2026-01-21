"""
WebSocket Server - 통합 버전

Phase 1-5 검증 완료된 모든 기능 통합:
- JWT 인증
- 콜백 패턴 (request_available_data, request_api, clarification_request)
- Rate Limiting
- Heartbeat (Ping/Pong)
- 다중 사용자 연결 관리
"""

import asyncio
import json
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .auth import generate_token, validate_token, get_user_info, JWT_EXPIRY_SECONDS
from .callbacks import PendingCallbacks, CallbackTimeoutError
from .connection_manager import ConnectionManager, ConnectionInfo
from .rate_limiter import RateLimiter
from .heartbeat import HeartbeatManager


# =============================================================================
# 설정
# =============================================================================

class Config:
    """서버 설정"""
    # 연결 정책
    SINGLE_SESSION_PER_USER = False  # True: 단일 연결만, False: 다중 연결 허용

    # Rate Limit
    SHARE_RATE_LIMIT = True          # True: 사용자 공유, False: 연결별 별도
    RATE_LIMIT_MAX_REQUESTS = 10
    RATE_LIMIT_WINDOW_SECONDS = 60

    # Heartbeat
    HEARTBEAT_INTERVAL = 30
    PONG_TIMEOUT = 10
    MAX_MISSED_PONGS = 3

    # Callback
    CALLBACK_TIMEOUT = 30.0


# =============================================================================
# 전역 인스턴스
# =============================================================================

connection_manager = ConnectionManager(single_session_per_user=Config.SINGLE_SESSION_PER_USER)
rate_limiter = RateLimiter(
    max_requests=Config.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=Config.RATE_LIMIT_WINDOW_SECONDS,
    share_limit=Config.SHARE_RATE_LIMIT
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("WebSocket Server Started (Integrated)")
    print(f"  SINGLE_SESSION_PER_USER: {Config.SINGLE_SESSION_PER_USER}")
    print(f"  SHARE_RATE_LIMIT: {Config.SHARE_RATE_LIMIT}")
    print(f"  RATE_LIMIT: {Config.RATE_LIMIT_MAX_REQUESTS} req / {Config.RATE_LIMIT_WINDOW_SECONDS}s")
    print("=" * 50)
    yield
    print("Server stopped")


app = FastAPI(lifespan=lifespan, title="OpsNow Copilot WebSocket")

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
    """JWT 토큰 발급"""
    token = generate_token(username=username, name=name)
    return {"access_token": token, "token_type": "Bearer", "expires_in": JWT_EXPIRY_SECONDS}


@app.get("/api/connections")
async def get_connections():
    """연결 현황 조회"""
    return {
        "stats": connection_manager.get_stats(),
        "connections": connection_manager.get_all_connections(),
        "settings": {
            "singleSessionPerUser": Config.SINGLE_SESSION_PER_USER,
            "shareRateLimit": Config.SHARE_RATE_LIMIT
        }
    }


@app.post("/api/rate-limit/reset")
async def reset_rate_limit(username: str, connection_id: str = ""):
    """Rate Limit 초기화"""
    rate_limiter.reset(username, connection_id)
    return {"message": f"Rate limit reset for {username}"}


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

    # 3. 연결 관리자에 추가
    old_connection = connection_manager.add(conn_info)

    # 기존 연결 끊기 (SINGLE_SESSION_PER_USER=True일 때)
    if old_connection:
        try:
            await old_connection.websocket.close(
                code=4002,
                reason="New connection from same user"
            )
            print(f"[{timestamp}] 기존 연결 종료: {username}")
        except Exception:
            pass

    conn_count = connection_manager.get_connection_count(username)
    print(f"[{timestamp}] 연결 성공: {username} (connId: {connection_id[:8]}, 총 {conn_count}개)")

    # 4. 연결 수락
    await websocket.accept()

    # 5. 콜백 매니저 (연결별)
    callbacks = PendingCallbacks(default_timeout=Config.CALLBACK_TIMEOUT)

    # 6. connected 메시지
    rate_status = rate_limiter.get_status(username, connection_id)
    await websocket.send_json({
        "type": "connected",
        "serverTime": datetime.now().isoformat(),
        "user": user_info,
        "connectionId": connection_id,
        "connectionCount": conn_count,
        "rateLimit": rate_status,
        "settings": {
            "singleSessionPerUser": Config.SINGLE_SESSION_PER_USER,
            "shareRateLimit": Config.SHARE_RATE_LIMIT
        }
    })

    # 7. Heartbeat 매니저
    heartbeat = HeartbeatManager(
        websocket=websocket,
        username=username,
        connection_id=connection_id,
        interval=Config.HEARTBEAT_INTERVAL,
        pong_timeout=Config.PONG_TIMEOUT,
        max_missed_pongs=Config.MAX_MISSED_PONGS
    )
    await heartbeat.start()

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            # pong 처리
            if msg_type == "pong":
                heartbeat.on_pong_received()
                continue

            # Rate Limit 상태 조회
            if msg_type == "get_rate_limit":
                status_info = rate_limiter.get_status(username, connection_id)
                await websocket.send_json({
                    "type": "rate_limit_status",
                    "rateLimit": status_info
                })
                continue

            # 콜백 응답 처리
            if msg_type in ["available_data", "api_result", "human_response"]:
                request_id = data.get("requestId")
                if request_id and callbacks.is_pending(request_id):
                    callbacks.resolve(request_id, data)
                continue

            # query 처리
            if msg_type == "query":
                allowed, rate_info = rate_limiter.is_allowed(username, connection_id)

                if not allowed:
                    await websocket.send_json({
                        "type": "error",
                        "code": "RATE_LIMITED",
                        "message": f"요청 한도 초과. {rate_info.get('retry_after', 60)}초 후 재시도하세요.",
                        "rateLimit": rate_info
                    })
                    continue

                query = data.get("query", "")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}:{connection_id[:8]}] query: {query}")

                # 콜백 예시: request_available_data
                # request_id, future = callbacks.create(callback_type="data")
                # await websocket.send_json({
                #     "type": "request_available_data",
                #     "requestId": request_id,
                #     "dataTypes": ["cost", "asset"]
                # })
                # try:
                #     result = await asyncio.wait_for(future, timeout=10.0)
                # except asyncio.TimeoutError:
                #     callbacks.cancel(request_id)

                # 간단한 응답
                await asyncio.sleep(0.3)
                await websocket.send_json({
                    "type": "response",
                    "answer": f"**[{username}]** 질문에 대한 응답\n\n> {query}\n\n처리 완료",
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
        await heartbeat.stop()
        callbacks.cancel_all()
        connection_manager.remove(connection_id)
        remaining = connection_manager.get_connection_count(username)
        print(f"  -> {username} 남은 연결: {remaining}개")


@app.get("/")
async def root():
    return HTMLResponse(content="""
    <html>
    <head><title>WebSocket PoC - Integrated</title></head>
    <body>
        <h1>WebSocket PoC - Integrated Version</h1>
        <p>Phase 1-5 검증 완료된 모든 기능 통합</p>
        <ul>
            <li>JWT 인증</li>
            <li>콜백 패턴</li>
            <li>Rate Limiting</li>
            <li>Heartbeat (Ping/Pong)</li>
            <li>다중 사용자 연결 관리</li>
        </ul>
        <p>client.html 파일을 브라우저에서 열어 테스트하세요.</p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
