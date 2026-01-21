"""
Phase 2: WebSocket JWT 토큰 인증 PoC

검증 항목:
- ws://{host}/ws/copilot?token={JWT} 연결
- JWT 검증 성공 → 연결 허용, payload에서 user_id 추출
- 토큰 없음 → 1008 (Policy Violation) 연결 거부
- 토큰 만료/서명 무효 → 4001 WebSocket close code

실제 환경과의 차이:
- 실제: Keycloak JWKS로 RS256 검증
- Mock: 로컬 secret key로 HS256 검증
"""

import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from auth import generate_token, validate_token, get_user_info, JWT_EXPIRY_SECONDS

# 하트비트 주기 (초)
HEARTBEAT_INTERVAL = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명주기 관리"""
    print("Server started - JWT Auth Mode")
    yield
    print("Server stopped")


app = FastAPI(lifespan=lifespan)

# CORS 설정 (로컬 테스트용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REST API (토큰 발급용 - 테스트 전용)
# =============================================================================

@app.post("/api/auth/token")
async def create_token(
    user_id: str = None,
    username: str = "test@example.com",
    name: str = "테스트 사용자",
    expires_in: int = JWT_EXPIRY_SECONDS
):
    """
    테스트용 JWT 토큰 발급 API

    실제 환경에서는 Keycloak이 토큰을 발급
    """
    token = generate_token(
        user_id=user_id,
        username=username,
        name=name,
        expires_in=expires_in
    )

    print(f"[Token] JWT 발급: {username}")

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires_in
    }


@app.post("/api/auth/token/expired")
async def create_expired_token(
    username: str = "test@example.com",
    name: str = "테스트 사용자"
):
    """
    만료된 토큰 발급 (테스트용)
    """
    token = generate_token(
        username=username,
        name=name,
        expires_in=-1  # 이미 만료됨
    )

    return {
        "access_token": token,
        "token_type": "Bearer",
        "note": "이 토큰은 이미 만료되었습니다"
    }


@app.get("/api/auth/verify")
async def verify_token_api(token: str):
    """
    토큰 검증 API (디버깅용)
    """
    payload, error, status_code = validate_token(token)

    if error:
        return JSONResponse(
            status_code=status_code,
            content={"valid": False, "error": error}
        )

    return {
        "valid": True,
        "user": get_user_info(payload),
        "expires_at": datetime.fromtimestamp(payload["exp"]).isoformat()
    }


# =============================================================================
# WebSocket
# =============================================================================

async def heartbeat_loop(websocket: WebSocket):
    """연결 유지를 위한 주기적 ping 전송"""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping"})
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ping 전송")
    except Exception:
        pass


@app.websocket("/ws/copilot")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None)
):
    """
    WebSocket 엔드포인트

    연결: ws://localhost:8000/ws/copilot?token={JWT}
    """
    timestamp = datetime.now().strftime('%H:%M:%S')

    # 1. 토큰 존재 여부 확인
    if not token:
        print(f"[{timestamp}] 연결 거부: 토큰 없음 → 1008")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. JWT 검증
    payload, error, status_code = validate_token(token)

    if error:
        print(f"[{timestamp}] 연결 거부: {error} → 4001")
        # 4001: 커스텀 코드 (토큰 검증 실패)
        await websocket.close(code=4001, reason=error)
        return

    # 3. 사용자 정보 추출
    user_info = get_user_info(payload)
    user_id = user_info["user_id"]
    username = user_info["username"]
    name = user_info["name"]

    print(f"[{timestamp}] 연결 성공: {username} ({name})")

    # 4. 연결 수락
    await websocket.accept()

    # 5. connected 메시지 전송
    await websocket.send_json({
        "type": "connected",
        "serverTime": datetime.now().isoformat(),
        "user": {
            "id": user_id,
            "username": username,
            "name": name,
            "companyId": user_info["company_id"],
            "roles": user_info["roles"]
        }
    })

    # 6. 하트비트 태스크 시작
    heartbeat_task = asyncio.create_task(heartbeat_loop(websocket))

    try:
        while True:
            # 7. 메시지 수신
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}] 수신: {msg_type}")

            # 8. 메시지 타입별 처리
            if msg_type == "query":
                query = data.get("query", "")
                print(f"  - 질문: {query}")

                await websocket.send_json({
                    "type": "response",
                    "answer": f"**{name}님의 질문**\n\n> {query}\n\nJWT 인증이 완료된 연결입니다.\n\n**사용자 정보:**\n- ID: `{user_id[:8]}...`\n- Email: `{username}`\n- 역할: `{', '.join(user_info['roles'][:2])}`",
                    "suggestions": [
                        {"type": "follow_up", "text": "더 알려줘", "query": "자세히 설명해줘"}
                    ]
                })

            elif msg_type == "pong":
                print(f"  - pong 수신")

            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": f"알 수 없는 메시지 타입: {msg_type}",
                    "retryable": False
                })

    except WebSocketDisconnect:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}] 연결 종료")
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] JSON 파싱 에러: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "INVALID_MESSAGE",
            "message": "잘못된 JSON 형식",
            "retryable": False
        })
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 에러: {e}")
    finally:
        heartbeat_task.cancel()


# =============================================================================
# 테스트 페이지
# =============================================================================

@app.get("/")
async def get_test_page():
    return HTMLResponse(content="""
    <html>
    <head><title>WebSocket PoC - Phase 2 (JWT Auth)</title></head>
    <body>
        <h1>WebSocket JWT 인증 테스트</h1>

        <h2>1. JWT 토큰 발급 (테스트용)</h2>
        <pre>POST /api/auth/token?username=test@example.com&name=테스트</pre>

        <h2>2. WebSocket 연결</h2>
        <pre>ws://localhost:8000/ws/copilot?token={JWT}</pre>

        <h2>3. 테스트 시나리오</h2>
        <ul>
            <li>✅ 유효한 JWT로 연결 → 성공, 사용자 정보 포함</li>
            <li>❌ 토큰 없이 연결 → 1008 코드로 거부</li>
            <li>❌ 잘못된 토큰으로 연결 → 4001 코드로 거부</li>
            <li>❌ 만료된 토큰으로 연결 → 4001 코드로 거부</li>
        </ul>

        <h2>4. JWT Payload 구조</h2>
        <pre>
{
  "sub": "user-uuid",
  "preferred_username": "user@example.com",
  "name": "홍길동",
  "currentCompanyId": "company-uuid",
  "realm_access": { "roles": ["platform_admin"] },
  "exp": 1234567890,
  "iat": 1234567890,
  "iss": "https://sso.opsnow360.io/realms/OPSNOW"
}
        </pre>

        <p>client.html 파일을 브라우저에서 열어 테스트하세요.</p>
        <p><a href="/docs">API 문서</a></p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)