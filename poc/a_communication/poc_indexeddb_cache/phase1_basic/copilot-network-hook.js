/**
 * Copilot Network Hook — fetch + XHR 오버라이드
 *
 * 브라우저의 fetch/XMLHttpRequest를 래핑하여
 * API 응답을 가로채고 IndexedDB(CopilotCache)에 저장한다.
 * 원본 응답은 변경 없이 그대로 반환한다.
 *
 * 의존: copilot-cache.js (window.CopilotCache)
 */

(function () {
  'use strict';

  // CopilotCache 의존성 확인
  if (!window.CopilotCache) {
    console.error('[CopilotNetworkHook] CopilotCache가 로드되지 않았습니다.');
    return;
  }

  const cache = window.CopilotCache;

  // ─── 유틸 ───

  /**
   * 저장 대상 URL인지 판별 (Phase 1: /api/ 포함 URL만 대상)
   */
  function shouldCapture(url) {
    try {
      const parsed = new URL(url, location.origin);
      return parsed.pathname.includes('/api/');
    } catch {
      return false;
    }
  }

  /**
   * 저장 키 생성 (URL의 pathname + search)
   */
  function buildKey(url) {
    try {
      const parsed = new URL(url, location.origin);
      return parsed.pathname + parsed.search;
    } catch {
      return url;
    }
  }

  /**
   * fire-and-forget 저장 — 에러가 발생해도 원본 흐름에 영향 없음
   */
  function saveToCache(key, data, meta) {
    try {
      cache.put(key, data, meta).catch((err) => {
        console.warn('[CopilotNetworkHook] IndexedDB 저장 실패:', err);
      });
    } catch (err) {
      console.warn('[CopilotNetworkHook] 저장 시도 실패:', err);
    }
  }

  // ─── fetch Override ───

  const originalFetch = window.fetch;

  window.fetch = function (...args) {
    const request = new Request(...args);
    const url = request.url;
    const method = request.method;

    return originalFetch.apply(this, args).then((response) => {
      if (shouldCapture(url) && response.ok) {
        // clone()으로 원본 응답 보존
        const cloned = response.clone();
        cloned
          .json()
          .then((data) => {
            const key = buildKey(url);
            saveToCache(key, data, {
              url,
              method,
              status: response.status,
            });
            console.log('[CopilotNetworkHook][fetch] 저장:', key);
          })
          .catch(() => {
            // JSON 파싱 실패 — 비 JSON 응답, 스킵
          });
      }
      return response; // 원본 응답 그대로 반환
    });
  };

  console.log('[CopilotNetworkHook] fetch override 완료');

  // ─── XHR Override ───

  const OriginalXHR = window.XMLHttpRequest;
  const originalOpen = OriginalXHR.prototype.open;
  const originalSend = OriginalXHR.prototype.send;

  OriginalXHR.prototype.open = function (method, url, ...rest) {
    this._copilot = {
      method: method,
      url: url,
    };
    return originalOpen.call(this, method, url, ...rest);
  };

  OriginalXHR.prototype.send = function (...args) {
    const xhr = this;
    const { method, url } = xhr._copilot || {};

    if (url && shouldCapture(url)) {
      xhr.addEventListener('load', function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            const key = buildKey(url);
            saveToCache(key, data, {
              url,
              method,
              status: xhr.status,
            });
            console.log('[CopilotNetworkHook][XHR] 저장:', key);
          } catch {
            // JSON 파싱 실패 — 스킵
          }
        }
      });
    }

    return originalSend.apply(this, args);
  };

  console.log('[CopilotNetworkHook] XHR override 완료');

  // ─── Public API (디버깅용) ───

  window.CopilotNetworkHook = {
    isActive: true,
    shouldCapture,
    buildKey,
  };
})();
