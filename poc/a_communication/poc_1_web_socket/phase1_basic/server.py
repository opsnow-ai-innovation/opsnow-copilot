"""
Phase 1: WebSocket 기본 연결 PoC

검증 항목:
- WebSocket 연결 핸드셰이크
- connected 메시지 전송
- query → response 기본 흐름
- ping/pong 하트비트
"""

import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

# 하트비트 주기 (초)
HEARTBEAT_INTERVAL = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명주기 관리"""
    print("Server started")
    yield
    print("Server stopped")


app = FastAPI(lifespan=lifespan)


async def heartbeat_loop(websocket: WebSocket):
    """연결 유지를 위한 주기적 ping 전송"""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping"})
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ping 전송")
    except Exception:
        pass  # 연결 종료 시 자연스럽게 종료


@app.websocket("/ws/copilot")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트"""
    await websocket.accept()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 클라이언트 연결됨")

    # 1. connected 메시지 전송
    await websocket.send_json({
        "type": "connected",
        "serverTime": datetime.now().isoformat()
    })

    # 2. 하트비트 태스크 시작
    heartbeat_task = asyncio.create_task(heartbeat_loop(websocket))

    try:
        while True:
            # 3. 메시지 수신
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            print(f"[{datetime.now().strftime('%H:%M:%S')}] 수신: {msg_type}")

            # 4. 메시지 타입별 처리
            if msg_type == "query":
                # query → response 기본 흐름
                query = data.get("query", "")
                dom_context = data.get("domContext", "")
                page = data.get("page", {})

                print(f"  - 질문: {query}")
                print(f"  - 페이지: {page.get('url', 'N/A')}")

                # 간단한 응답 (실제로는 AI 처리)
                await websocket.send_json({
                    "type": "response",
                    "answer": f"**질문을 받았습니다**\n\n> {query}\n\n현재 페이지: {page.get('title', 'N/A')}",
                    "suggestions": [
                        {"type": "follow_up", "text": "더 자세히 알려주세요", "query": "자세한 설명 부탁드립니다"},
                        {"type": "related", "text": "비용 분석 보기", "query": "비용 분석해줘"}
                    ]
                })

            elif msg_type == "pong":
                # 하트비트 응답
                print(f"  - pong 수신 (연결 유지 확인)")

            else:
                # 알 수 없는 메시지 타입
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": f"알 수 없는 메시지 타입: {msg_type}",
                    "retryable": False
                })

    except WebSocketDisconnect:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 클라이언트 연결 종료")
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


# 간단한 테스트용 HTML 페이지 제공
@app.get("/")
async def get_test_page():
    return HTMLResponse(content="""
    <html>
    <head><title>WebSocket PoC - Phase 1</title></head>
    <body>
        <h1>WebSocket 테스트</h1>
        <p>client.html 파일을 브라우저에서 열어주세요.</p>
        <p>또는 <a href="/docs">API 문서</a>를 확인하세요.</p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
