/**
 * Copilot WebSocket Handler — WebSocket 콜백 → IndexedDB 조회/실행
 *
 * Phase 4: 서버 콜백 메시지를 수신하여 IndexedDB에서 데이터를 조회/실행하고 응답
 *
 * 처리하는 서버→클라이언트 콜백:
 *   - request_available_data → IndexedDB 키 목록 조회 → available_data 응답
 *   - request_api            → IndexedDB 데이터 조회   → api_result 응답
 *   - execute_code           → 코드 샌드박스 실행       → code_result 응답
 *   - ping                   → pong 응답
 *
 * 의존: copilot-cache.js (window.CopilotCache)
 */

(function () {
  'use strict';

  const cache = window.CopilotCache;
  if (!cache) {
    console.error('[CopilotWSHandler] CopilotCache가 로드되지 않았습니다.');
    return;
  }

  // ─── 설정 ───

  const LARGE_DATA_THRESHOLD = 100 * 1024; // 100KB — 초과 시 스키마 방식 전환 신호

  // ─── 상태 ───

  let ws = null;
  let isConnected = false;
  const eventHandlers = {};

  // ─── 이벤트 시스템 ───

  function on(event, handler) {
    if (!eventHandlers[event]) eventHandlers[event] = [];
    eventHandlers[event].push(handler);
  }

  function off(event, handler) {
    if (!eventHandlers[event]) return;
    eventHandlers[event] = eventHandlers[event].filter((h) => h !== handler);
  }

  function emit(event, data) {
    (eventHandlers[event] || []).forEach((h) => {
      try {
        h(data);
      } catch (e) {
        console.warn('[CopilotWSHandler] 이벤트 핸들러 에러:', e);
      }
    });
  }

  // ─── WebSocket 연결 ───

  function connect(url) {
    if (ws) {
      ws.close();
    }

    ws = new WebSocket(url);

    ws.onopen = () => {
      isConnected = true;
      console.log('[CopilotWSHandler] 연결 성공:', url);
      emit('open', { url });
    };

    ws.onclose = (e) => {
      isConnected = false;
      console.log(`[CopilotWSHandler] 연결 종료: code=${e.code}, reason=${e.reason}`);
      emit('close', { code: e.code, reason: e.reason });
    };

    ws.onerror = (e) => {
      console.error('[CopilotWSHandler] 연결 에러:', e);
      emit('error', { error: e });
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log(`[CopilotWSHandler] ← 수신: ${msg.type}${msg.requestId ? ' (requestId: ...' + msg.requestId.slice(-8) + ')' : ''}`);
        emit('message', msg);
        await handleMessage(msg);
      } catch (err) {
        console.error('[CopilotWSHandler] 메시지 처리 에러:', err);
      }
    };

    return ws;
  }

  function disconnect() {
    if (ws) {
      ws.close();
      ws = null;
    }
  }

  function send(msg) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[CopilotWSHandler] WebSocket 미연결 상태');
      return false;
    }
    console.log(`[CopilotWSHandler] → 전송: ${msg.type}${msg.requestId ? ' (requestId: ...' + msg.requestId.slice(-8) + ')' : ''}`);
    ws.send(JSON.stringify(msg));
    return true;
  }

  // ─── 메시지 라우팅 ───

  async function handleMessage(msg) {
    switch (msg.type) {
      case 'connected':
        emit('server_connected', msg);
        break;

      case 'ping':
        send({ type: 'pong' });
        break;

      case 'request_available_data':
        await handleRequestAvailableData(msg);
        break;

      case 'request_api':
        await handleRequestApi(msg);
        break;

      case 'execute_code':
        await handleExecuteCode(msg);
        break;

      case 'response':
        emit('response', msg);
        break;

      case 'error':
        emit('server_error', msg);
        break;

      default:
        console.log('[CopilotWSHandler] 알 수 없는 메시지:', msg.type);
    }
  }

  // ─── request_available_data → available_data ───

  async function handleRequestAvailableData(msg) {
    try {
      const records = await cache.getAll();
      const data = records.map((r) => ({
        key: r.key,
        description: `${r.method} ${r.url}`,
        size: r.size || 0,
        menu: r.menu,
        timestamp: r.timestamp,
      }));

      send({
        type: 'available_data',
        requestId: msg.requestId,
        data: data,
      });

      emit('callback_sent', {
        callbackType: 'available_data',
        requestId: msg.requestId,
        count: data.length,
      });
    } catch (err) {
      console.error('[CopilotWSHandler] available_data 에러 (격리):', err);
      send({
        type: 'available_data',
        requestId: msg.requestId,
        data: [],
      });
    }
  }

  // ─── request_api → api_result ───

  async function handleRequestApi(msg) {
    try {
      const dataKey = msg.dataKey;
      const record = await cache.get(dataKey);

      if (!record) {
        send({
          type: 'api_result',
          requestId: msg.requestId,
          success: false,
          error: { code: 'NOT_FOUND', message: `키를 찾을 수 없음: ${dataKey}` },
        });
        return;
      }

      const dataSize = cache.getDataSize(record.data);

      if (dataSize >= LARGE_DATA_THRESHOLD) {
        // 대용량 → 스키마 방식 전환 신호
        send({
          type: 'api_result',
          requestId: msg.requestId,
          success: true,
          isLargeData: true,
          cacheKey: dataKey,
          data: null,
        });
      } else {
        send({
          type: 'api_result',
          requestId: msg.requestId,
          success: true,
          data: record.data,
        });
      }

      emit('callback_sent', {
        callbackType: 'api_result',
        requestId: msg.requestId,
        key: dataKey,
        size: dataSize,
      });
    } catch (err) {
      console.error('[CopilotWSHandler] api_result 에러 (격리):', err);
      send({
        type: 'api_result',
        requestId: msg.requestId,
        success: false,
        error: { code: 'INTERNAL_ERROR', message: err.message },
      });
    }
  }

  // ─── execute_code → code_result ───
  //
  // 서버(LLM)가 생성한 자체 완결형 JavaScript 코드를 실행.
  // 코드 안에서 CopilotCache.get() 등을 직접 호출하여
  // 어떤 키의 데이터를 조회할지까지 코드가 결정한다.
  // 클라이언트는 코드만 실행하면 결과가 나온다.
  //
  // new Function()으로 샌드박스 실행 (PoC 수준).
  // 프로덕션에서는 Web Worker 또는 iframe 샌드박스 사용 권장.

  async function handleExecuteCode(msg) {
    try {
      const { code, requestId } = msg;

      console.log('[CopilotWSHandler] execute_code 수신 코드:\n' + code);

      // 샌드박스 실행: CopilotCache만 전달 — 코드가 직접 조회/처리
      const fn = new Function(
        'CopilotCache',
        `return (async () => { ${code} })();`
      );

      const result = await fn(cache);

      send({
        type: 'code_result',
        requestId: requestId,
        success: true,
        result: result,
      });

      emit('callback_sent', {
        callbackType: 'code_result',
        requestId: requestId,
      });
    } catch (err) {
      // 에러 격리: 코드 실행 실패해도 페이지에 영향 없음
      console.error('[CopilotWSHandler] execute_code 에러 (격리):', err);
      send({
        type: 'code_result',
        requestId: msg.requestId,
        success: false,
        error: {
          type: err.constructor.name,
          message: err.message,
        },
      });
    }
  }

  // ─── 질의 전송 ───

  function sendQuery(query, options = {}) {
    return send({
      type: 'query',
      query: query,
      mode: options.mode || 'normal',
      domContext: options.domContext || '',
      page: {
        url: location.href,
        title: document.title,
      },
    });
  }

  // ─── Public API ───

  window.CopilotWSHandler = {
    connect,
    disconnect,
    send,
    sendQuery,
    on,
    off,
    isConnected: () => isConnected,
    getWebSocket: () => ws,
  };
})();
