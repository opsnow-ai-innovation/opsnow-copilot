"""
WebSocket Server — Phase 4 IndexedDB 콜백 연동 테스트용

실행:
  pip install websockets
  python ws-server.py

포트: 8765

지원하는 query 모드:
  - normal (기본):        request_available_data → request_api → response
  - execute_code:         request_available_data → execute_code → response
  - execute_code_error:   execute_code(잘못된 코드) → 에러 격리 확인
"""

import asyncio
import json
import secrets
import time

try:
    import websockets
except ImportError:
    print("=" * 55)
    print("  websockets 라이브러리가 필요합니다:")
    print("    pip install websockets")
    print("=" * 55)
    exit(1)

PORT = 8765


# ─── 유틸 ───

def generate_request_id():
    """One-Time Token 생성 (형식: {timestamp_ms}-{random})"""
    timestamp = int(time.time() * 1000)
    random_part = secrets.token_urlsafe(12)
    return f"{timestamp}-{random_part}"


def ts():
    """현재 시각 문자열"""
    return time.strftime("%H:%M:%S")


# ─── 콜백 응답 타입 ───

CALLBACK_TYPES = {
    "available_data",
    "api_result",
    "code_result",
    "schema_response",
    "human_response",
}


# ─── 콜백 요청 헬퍼 ───

async def request_callback(websocket, pending, msg_type, payload, timeout=10.0):
    """
    서버 → 클라이언트 콜백 요청 전송 후 응답 대기.

    1. requestId 생성 + Future 등록
    2. 메시지 전송
    3. 클라이언트 응답 대기 (timeout)
    """
    request_id = generate_request_id()

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending[request_id] = future

    payload["type"] = msg_type
    payload["requestId"] = request_id

    await websocket.send(json.dumps(payload))
    print(f"  [{ts()}] -> {msg_type} (requestId: ...{request_id[-8:]})")

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        pending.pop(request_id, None)
        print(f"  [{ts()}] TIMEOUT: {msg_type} ({timeout}s)")
        return None


# ─── 응답 전송 헬퍼 ───

async def send_response(websocket, answer, sources=None):
    """최종 응답(response) 메시지 전송"""
    await websocket.send(json.dumps({
        "type": "response",
        "answer": answer,
        "sources": sources or [],
    }))
    print(f"  [{ts()}] -> response")


# ─── 쿼리 처리 ───

async def process_query(websocket, pending, query, mode):
    """
    query 수신 후 콜백 흐름 처리.

    mode:
      - "normal":              request_available_data → request_api → response
      - "execute_code":        request_available_data → execute_code → response
      - "execute_code_error":  execute_code(잘못된 코드) → 에러 격리 확인
    """
    try:
        # ─── 모드: execute_code_error ───
        # 일부러 잘못된 코드를 보내 에러 격리가 동작하는지 확인
        if mode == "execute_code_error":
            code_result = await request_callback(
                websocket, pending, "execute_code",
                {
                    "code": "undefinedFunction(); return 'should not reach';",
                },
                timeout=10.0,
            )

            if not code_result:
                await send_response(websocket, "TIMEOUT: execute_code 응답 없음")
                return

            if code_result.get("success"):
                await send_response(
                    websocket,
                    "!! 에러가 예상됐지만 성공했습니다:\n\n"
                    f"```json\n{json.dumps(code_result.get('result'), ensure_ascii=False)}\n```",
                )
            else:
                error = code_result.get("error", {})
                await send_response(
                    websocket,
                    "## 에러 격리 확인 완료\n\n"
                    "잘못된 코드 실행 시 에러가 정상적으로 포착되었습니다.\n\n"
                    f"- 에러 타입: `{error.get('type', 'Unknown')}`\n"
                    f"- 에러 메시지: `{error.get('message', 'Unknown')}`\n\n"
                    "> 원본 페이지 동작에 영향 없음 확인",
                )
            return

        # ─── Step 1: request_available_data ───
        available = await request_callback(
            websocket, pending, "request_available_data", {}, timeout=10.0
        )

        if not available:
            await send_response(websocket, "TIMEOUT: request_available_data 응답 없음")
            return

        data_list = available.get("data", [])

        # 캐시 없음 (시나리오 2)
        if not data_list:
            await send_response(
                websocket,
                "## IndexedDB에 데이터 없음\n\n"
                f"질문: {query}\n\n"
                "저장된 API 데이터가 없습니다.\n"
                "먼저 API 요청을 실행하여 데이터를 저장한 후 질문해 주세요.\n\n"
                "> Smart Fallback: 관련 메뉴로 이동을 안내합니다.",
            )
            return

        # ─── 모드: execute_code ───
        # 실제 서비스: LLM이 available_data 스키마를 보고 자체 완결형 코드 생성
        # PoC: LLM이 생성할 코드를 하드코딩 (시뮬레이션)
        if mode == "execute_code":
            available_keys = [d.get("key") for d in data_list]
            print(f"  [{ts()}] execute_code (available keys: {available_keys})")

            # ── 하드코딩된 실행 코드 (LLM 생성 시뮬레이션) ──
            # 코드가 직접 CopilotCache.get()으로 IndexedDB 조회
            code = (
                "const record = await CopilotCache.get('/api/cost/summary');\n"
                "if (!record) return { error: '/api/cost/summary not found' };\n"
                "const data = record.data;\n"
                "if (data && data.breakdown) {\n"
                "  return data.breakdown.sort((a, b) => b.cost - a.cost).slice(0, 3);\n"
                "}\n"
                "return data;"
            )

            print(f"  [{ts()}] execute_code 전송 코드:\n{code}")

            code_result = await request_callback(
                websocket, pending, "execute_code",
                {"code": code},
                timeout=10.0,
            )

            if not code_result:
                await send_response(websocket, "TIMEOUT: execute_code 응답 없음")
                return

            if code_result.get("success"):
                result_data = code_result.get("result")
                result_json = json.dumps(result_data, ensure_ascii=False, indent=2)
                await send_response(
                    websocket,
                    "## execute_code 실행 결과\n\n"
                    f"질문: {query}\n\n"
                    "IndexedDB 키: `/api/cost/summary`\n\n"
                    f"```json\n{result_json}\n```",
                    sources=["/api/cost/summary"],
                )
            else:
                error = code_result.get("error", {})
                await send_response(
                    websocket,
                    "## execute_code 실행 에러\n\n"
                    f"`{error.get('type', 'Error')}`: {error.get('message', 'Unknown')}",
                )
            return

        # ─── 모드: normal — request_api ───

        # 질의 키워드로 가장 적합한 키 선택 (LLM 시뮬레이션)
        selected_key = data_list[0].get("key")
        for item in data_list:
            key = item.get("key", "")
            if "cost" in query.lower() and "cost" in key:
                selected_key = key
                break
            elif "asset" in query.lower() and "asset" in key:
                selected_key = key
                break
            elif "billing" in query.lower() and "billing" in key:
                selected_key = key
                break

        # Step 2: request_api
        api_result = await request_callback(
            websocket, pending, "request_api",
            {"dataKey": selected_key},
            timeout=10.0,
        )

        if not api_result:
            await send_response(websocket, "TIMEOUT: request_api 응답 없음")
            return

        if api_result.get("success"):
            if api_result.get("isLargeData"):
                await send_response(
                    websocket,
                    "## 대용량 데이터 감지\n\n"
                    f"IndexedDB 키: `{selected_key}`\n\n"
                    "데이터가 100KB 이상입니다. 스키마 방식 전환이 필요합니다.\n"
                    "(PoC에서는 대용량 감지까지 확인)",
                    sources=[selected_key],
                )
            else:
                result_data = api_result.get("data")
                preview = json.dumps(result_data, ensure_ascii=False, indent=2)
                if len(preview) > 500:
                    preview = preview[:500] + "\n... (truncated)"

                keys_list = ", ".join([f"`{d.get('key')}`" for d in data_list])
                await send_response(
                    websocket,
                    "## IndexedDB 데이터 조회 성공\n\n"
                    f"질문: {query}\n\n"
                    f"사용 가능한 키: {keys_list}\n"
                    f"선택된 키: `{selected_key}`\n\n"
                    f"```json\n{preview}\n```",
                    sources=[selected_key],
                )
        else:
            error = api_result.get("error", {})
            await send_response(
                websocket,
                "## 데이터 조회 실패\n\n"
                f"`{error.get('code')}`: {error.get('message')}",
            )

    except Exception as e:
        print(f"  [{ts()}] ERROR: process_query: {e}")
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e),
            }))
        except Exception:
            pass


# ─── WebSocket 핸들러 ───

async def handler(websocket):
    """WebSocket 연결별 메시지 처리 루프"""
    pending = {}  # requestId → asyncio.Future (연결별 독립)

    addr = websocket.remote_address
    print(f"[{ts()}] Connected: {addr}")

    # connected 메시지 전송
    await websocket.send(json.dumps({
        "type": "connected",
        "serverTime": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }))

    try:
        async for raw_msg in websocket:
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": "Invalid JSON",
                }))
                continue

            msg_type = msg.get("type")

            # 콜백 응답 처리 — Future resolve
            if msg_type in CALLBACK_TYPES:
                request_id = msg.get("requestId")
                if request_id and request_id in pending:
                    future = pending.pop(request_id)
                    if not future.done():
                        future.set_result(msg)
                    print(f"  [{ts()}] <- {msg_type} (requestId: ...{request_id[-8:]})")
                continue

            # pong
            if msg_type == "pong":
                continue

            # query → 비동기 처리 태스크 생성
            if msg_type == "query":
                query = msg.get("query", "")
                mode = msg.get("mode", "normal")
                print(f"  [{ts()}] Query: \"{query}\" (mode: {mode})")
                asyncio.create_task(process_query(websocket, pending, query, mode))
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": f"Unknown type: {msg_type}",
                }))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # 모든 대기 중 콜백 취소
        for rid, future in pending.items():
            if not future.done():
                future.cancel()
        pending.clear()
        print(f"[{ts()}] Disconnected: {addr}")


# ─── 서버 시작 ───

async def main():
    async with websockets.serve(handler, "localhost", PORT):
        print("=" * 55)
        print(f"  WebSocket Server (Phase 4) — ws://localhost:{PORT}")
        print("=" * 55)
        print()
        print("  콜백 흐름:")
        print("    normal:             query → request_available_data → request_api → response")
        print("    execute_code:       query → request_available_data → execute_code → response")
        print("    execute_code_error: query → execute_code(broken) → error response")
        print()
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
