"""
Phase 3: WebSocket 콜백 패턴 PoC

검증 항목:
- request_available_data → available_data 흐름
- request_api → api_result 흐름
- clarification_request → human_response 흐름
- One-Time Token (requestId) 매칭
- 타임아웃 처리 (asyncio.wait_for)

콜백 흐름:
1. 클라이언트: query 전송
2. 서버: request_available_data 전송 (requestId 생성)
3. 서버: Future 생성 및 대기 (await)
4. 클라이언트: IndexedDB 목록 조회
5. 클라이언트: available_data 응답 (requestId 포함)
6. 서버: Future resolve, 처리 계속
7. 서버: response 전송
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 상위 디렉토리의 auth 모듈 import
sys.path.append(str(Path(__file__).parent.parent / "phase2_auth"))
from auth import generate_token, validate_token, get_user_info, JWT_EXPIRY_SECONDS

from pending_callbacks import PendingCallbacks, CallbackTimeoutError, CallbackError

# 설정
HEARTBEAT_INTERVAL = 30
CALLBACK_TIMEOUT = {
    "available_data": 10,   # IndexedDB 목록 조회
    "api": 60,              # API 데이터 조회
    "human": 120,           # 사용자 입력 대기
    "schema": 10,           # 스키마 조회
    "code": 10,             # 코드 실행
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server started - Callback Pattern Mode")
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
# REST API (토큰 발급용)
# =============================================================================

@app.post("/api/auth/token")
async def create_token(
    username: str = "test@example.com",
    name: str = "테스트 사용자"
):
    token = generate_token(username=username, name=name)
    return {"access_token": token, "token_type": "Bearer", "expires_in": JWT_EXPIRY_SECONDS}


# =============================================================================
# WebSocket 콜백 헬퍼 함수
# =============================================================================

async def request_available_data(
    websocket: WebSocket,
    callbacks: PendingCallbacks,
    timeout: float = None
) -> list[dict]:
    """
    클라이언트의 IndexedDB 데이터 목록 요청

    Returns:
        [{"key": "costSummary", "description": "비용 요약", "size": 1024}, ...]
    """
    timeout = timeout or CALLBACK_TIMEOUT["available_data"]
    request_id, future = callbacks.create(callback_type="available_data", timeout=timeout)

    await websocket.send_json({
        "type": "request_available_data",
        "requestId": request_id,
        "timeout": int(timeout * 1000)
    })

    print(f"  -> request_available_data 전송 (requestId: {request_id[:20]}...)")

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        return result.get("data", [])
    except asyncio.TimeoutError:
        callbacks.cancel(request_id)
        raise CallbackTimeoutError(request_id, timeout)


async def request_api_data(
    websocket: WebSocket,
    callbacks: PendingCallbacks,
    data_key: str,
    timeout: float = None
) -> dict:
    """
    클라이언트의 IndexedDB에서 특정 데이터 요청

    Args:
        data_key: IndexedDB 키 (available_data에서 선택)

    Returns:
        {"success": True, "data": {...}} 또는 {"success": False, "error": {...}}
    """
    timeout = timeout or CALLBACK_TIMEOUT["api"]
    request_id, future = callbacks.create(callback_type="api", timeout=timeout)

    await websocket.send_json({
        "type": "request_api",
        "requestId": request_id,
        "dataKey": data_key,
        "timeout": int(timeout * 1000)
    })

    print(f"  -> request_api 전송 (dataKey: {data_key}, requestId: {request_id[:20]}...)")

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        if not result.get("success"):
            error = result.get("error", {})
            raise CallbackError(request_id, error.get("code", "UNKNOWN"), error.get("message", "Unknown error"))
        return result
    except asyncio.TimeoutError:
        callbacks.cancel(request_id)
        raise CallbackTimeoutError(request_id, timeout)


async def request_clarification(
    websocket: WebSocket,
    callbacks: PendingCallbacks,
    question: str,
    options: list[str] = None,
    input_type: str = "text",
    timeout: float = None
) -> dict:
    """
    사용자에게 추가 정보 요청 (ask_human 도구)

    Args:
        question: 질문 텍스트
        options: 선택지 목록 (있는 경우)
        input_type: "text" | "select" | "confirm"

    Returns:
        {"response": "사용자 입력", "selectedOption": "선택한 옵션"}
    """
    timeout = timeout or CALLBACK_TIMEOUT["human"]
    request_id, future = callbacks.create(callback_type="human", timeout=timeout)

    await websocket.send_json({
        "type": "clarification_request",
        "requestId": request_id,
        "question": question,
        "options": options,
        "inputType": input_type,
        "timeout": int(timeout * 1000)
    })

    print(f"  -> clarification_request 전송 (question: {question[:30]}...)")

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        callbacks.cancel(request_id)
        raise CallbackTimeoutError(request_id, timeout)


# =============================================================================
# 쿼리 처리 (콜백 패턴 시연)
# =============================================================================

async def process_query(
    websocket: WebSocket,
    callbacks: PendingCallbacks,
    query: str,
    user_info: dict
) -> dict:
    """
    사용자 쿼리 처리 (콜백 패턴 시연)

    시나리오:
    1. IndexedDB 목록 요청 (request_available_data)
    2. 필요한 데이터 선택 후 요청 (request_api)
    3. 모호한 경우 사용자에게 질문 (clarification_request)
    4. 최종 응답 생성
    """
    name = user_info.get("name", "사용자")
    steps = []

    try:
        # Step 1: IndexedDB 목록 요청
        steps.append("1. IndexedDB 데이터 목록 요청")
        available_data = await request_available_data(websocket, callbacks)
        steps.append(f"   → {len(available_data)}개 데이터 확인: {[d['key'] for d in available_data]}")

        # Step 2: 데이터가 있으면 첫 번째 데이터 요청
        if available_data:
            first_key = available_data[0]["key"]
            steps.append(f"2. '{first_key}' 데이터 요청")
            api_result = await request_api_data(websocket, callbacks, first_key)
            data = api_result.get("data", {})
            steps.append(f"   → 데이터 수신: {str(data)[:50]}...")

        # Step 3: "모호한" 키워드가 있으면 사용자에게 질문
        if "모호" in query or "어떤" in query or "선택" in query:
            steps.append("3. 추가 정보 요청 (clarification)")
            clarification = await request_clarification(
                websocket, callbacks,
                question="어떤 정보를 원하시나요?",
                options=["비용 요약", "비용 추세", "리소스 목록"],
                input_type="select"
            )
            user_response = clarification.get("response", "")
            selected = clarification.get("selectedOption", "")
            steps.append(f"   → 사용자 응답: {selected or user_response}")

        # 최종 응답 생성
        steps_text = "\n".join(steps)
        answer = f"""**{name}님의 질문 처리 완료**

> {query}

### 콜백 패턴 실행 결과

```
{steps_text}
```

### 사용된 콜백
- `request_available_data` → `available_data`
- `request_api` → `api_result`
{"- `clarification_request` → `human_response`" if "모호" in query or "어떤" in query or "선택" in query else ""}
"""
        return {"success": True, "answer": answer}

    except CallbackTimeoutError as e:
        return {
            "success": False,
            "answer": f"**타임아웃 오류**\n\n콜백 응답 대기 시간 초과: {e.timeout}초"
        }
    except CallbackError as e:
        return {
            "success": False,
            "answer": f"**콜백 오류**\n\n[{e.code}] {e.message}"
        }


# =============================================================================
# WebSocket 엔드포인트
# =============================================================================

async def heartbeat_loop(websocket: WebSocket):
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping"})
    except Exception:
        pass


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
    print(f"[{timestamp}] 연결 성공: {username}")

    # 2. 연결 수락
    await websocket.accept()

    # 3. 세션별 콜백 관리자
    callbacks = PendingCallbacks()

    # 4. connected 메시지
    await websocket.send_json({
        "type": "connected",
        "serverTime": datetime.now().isoformat(),
        "user": user_info
    })

    # 5. 하트비트
    heartbeat_task = asyncio.create_task(heartbeat_loop(websocket))

    # 6. 메시지 큐 (쿼리 처리용)
    query_queue = asyncio.Queue()

    async def query_processor():
        """쿼리 처리 태스크 (메시지 수신과 분리)"""
        while True:
            try:
                query, query_data = await query_queue.get()
                print(f"  - 쿼리 처리 시작: {query}")

                # 콜백 패턴으로 처리
                result = await process_query(websocket, callbacks, query, user_info)

                await websocket.send_json({
                    "type": "response",
                    "answer": result["answer"],
                    "suggestions": [
                        {"type": "follow_up", "text": "다른 데이터 보기", "query": "다른 데이터 보여줘"},
                        {"type": "follow_up", "text": "모호한 질문", "query": "어떤 정보를 원하시나요?"}
                    ]
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"  쿼리 처리 에러: {e}")

    query_task = asyncio.create_task(query_processor())

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")
            request_id = data.get("requestId")

            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{username}] 수신: {msg_type}")

            # 콜백 응답 처리 (우선 처리)
            if msg_type == "available_data":
                if request_id and callbacks.resolve(request_id, data):
                    print(f"  <- available_data 수신 (requestId 매칭 성공)")
                else:
                    print(f"  <- available_data 수신 (requestId 매칭 실패: {request_id})")
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_TOKEN",
                        "message": f"유효하지 않은 requestId: {request_id}",
                        "requestId": request_id
                    })

            elif msg_type == "api_result":
                if request_id and callbacks.resolve(request_id, data):
                    print(f"  <- api_result 수신 (requestId 매칭 성공)")
                else:
                    print(f"  <- api_result 수신 (requestId 매칭 실패: {request_id})")
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_TOKEN",
                        "message": f"유효하지 않은 requestId: {request_id}",
                        "requestId": request_id
                    })

            elif msg_type == "human_response":
                if request_id and callbacks.resolve(request_id, data):
                    print(f"  <- human_response 수신 (requestId 매칭 성공)")
                else:
                    print(f"  <- human_response 수신 (requestId 매칭 실패: {request_id})")
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_TOKEN",
                        "message": f"유효하지 않은 requestId: {request_id}",
                        "requestId": request_id
                    })

            # 쿼리는 큐에 추가 (별도 태스크에서 처리)
            elif msg_type == "query":
                query = data.get("query", "")
                print(f"  - 질문 수신: {query}")
                await query_queue.put((query, data))

            elif msg_type == "pong":
                pass

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
        heartbeat_task.cancel()
        query_task.cancel()
        callbacks.cancel_all()  # 연결 종료 시 모든 대기 중인 콜백 취소


@app.get("/")
async def get_test_page():
    return HTMLResponse(content="""
    <html>
    <head><title>WebSocket PoC - Phase 3 (Callback)</title></head>
    <body>
        <h1>WebSocket 콜백 패턴 테스트</h1>
        <h2>콜백 흐름</h2>
        <pre>
1. 클라이언트: query 전송
2. 서버: request_available_data 전송 (requestId 생성)
3. 클라이언트: available_data 응답 (requestId 포함)
4. 서버: request_api 전송
5. 클라이언트: api_result 응답
6. 서버: response 전송
        </pre>
        <p>client.html 파일을 브라우저에서 열어 테스트하세요.</p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
