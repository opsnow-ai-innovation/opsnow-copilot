/**
 * Copilot Network Hook — fetch + XHR 오버라이드 + 필터링 + 메뉴 변경 감지 + 에러 격리
 *
 * Phase 3: Phase 2 전체 기능 + 모든 override 경로 에러 격리
 *          캐시 장애 시에도 원본 fetch/XHR 응답에 절대 영향 없음
 *          성능 측정 타이밍 훅 포함
 *
 * 의존: copilot-cache.js (window.CopilotCache)
 */

(function () {
  'use strict';

  if (!window.CopilotCache) {
    console.error('[CopilotNetworkHook] CopilotCache가 로드되지 않았습니다.');
    return;
  }

  const cache = window.CopilotCache;

  // ─── 필터링 설정 ───

  const FILTER = {
    urlPatterns: ['/api/'],
    excludePatterns: ['/auth/', '/login/', '/logout/', '/health'],
    methods: ['GET', 'POST'],
    contentTypes: ['application/json'],
  };

  // ─── 성능 측정 ───

  const perfLog = [];

  function recordPerf(type, url, overheadMs) {
    perfLog.push({ type, url, overheadMs, timestamp: Date.now() });
  }

  function getPerfLog() {
    return [...perfLog];
  }

  function clearPerfLog() {
    perfLog.length = 0;
  }

  // ─── 필터링 유틸 ───

  function shouldCaptureUrl(url) {
    try {
      const parsed = new URL(url, location.origin);
      const path = parsed.pathname;
      if (FILTER.excludePatterns.some((p) => path.includes(p))) return false;
      return FILTER.urlPatterns.some((p) => path.includes(p));
    } catch {
      return false;
    }
  }

  function shouldCaptureMethod(method) {
    return FILTER.methods.includes(method.toUpperCase());
  }

  function shouldCaptureContentType(contentType) {
    if (!contentType) return false;
    return FILTER.contentTypes.some((ct) => contentType.includes(ct));
  }

  function buildKey(url) {
    try {
      const parsed = new URL(url, location.origin);
      return parsed.pathname + parsed.search;
    } catch {
      return url;
    }
  }

  /**
   * fire-and-forget 저장 — 완전 격리, 절대 throw 안 함
   */
  function saveToCache(key, data, meta) {
    try {
      const t0 = performance.now();
      cache.put(key, data, meta).then((result) => {
        const overhead = performance.now() - t0;
        recordPerf('save', key, overhead);
        if (result) {
          console.log(`[CopilotNetworkHook] 저장: ${key} (${cache.getDataSize(data)} bytes, ${overhead.toFixed(2)}ms)`);
        }
      }).catch((err) => {
        console.warn('[CopilotNetworkHook] IndexedDB 저장 실패 (격리됨):', err.message);
      });
    } catch (err) {
      console.warn('[CopilotNetworkHook] 저장 시도 실패 (격리됨):', err.message);
    }
  }

  // ─── fetch Override (에러 격리) ───

  const originalFetch = window.fetch;

  window.fetch = function (...args) {
    let request;
    try {
      request = new Request(...args);
    } catch {
      // Request 생성 실패 — 원본 그대로 전달
      return originalFetch.apply(this, args);
    }

    const url = request.url;
    const method = request.method;

    if (!shouldCaptureMethod(method)) {
      return originalFetch.apply(this, args);
    }

    const t0 = performance.now();

    return originalFetch.apply(this, args).then((response) => {
      // 에러 격리: 캐시 로직 전체를 try-catch
      try {
        if (!shouldCaptureUrl(url)) return response;
        if (!response.ok) return response;

        const contentType = response.headers.get('Content-Type') || '';
        if (!shouldCaptureContentType(contentType)) return response;

        const cloned = response.clone();
        cloned
          .json()
          .then((data) => {
            const overhead = performance.now() - t0;
            recordPerf('fetch-intercept', url, overhead);
            const key = buildKey(url);
            saveToCache(key, data, { url, method, status: response.status });
          })
          .catch(() => {
            // JSON 파싱 실패 — 스킵 (격리됨)
          });
      } catch (err) {
        // 캐시 로직 에러 — 원본 응답에 영향 없음
        console.warn('[CopilotNetworkHook] fetch 캐시 에러 (격리됨):', err.message);
      }

      return response;
    });
  };

  console.log('[CopilotNetworkHook] fetch override 완료 (에러 격리)');

  // ─── XHR Override (에러 격리) ───

  const OriginalXHR = window.XMLHttpRequest;
  const originalOpen = OriginalXHR.prototype.open;
  const originalSend = OriginalXHR.prototype.send;

  OriginalXHR.prototype.open = function (method, url, ...rest) {
    try {
      this._copilot = { method, url };
    } catch {
      // 격리
    }
    return originalOpen.call(this, method, url, ...rest);
  };

  OriginalXHR.prototype.send = function (...args) {
    try {
      const xhr = this;
      const { method, url } = xhr._copilot || {};

      if (url && shouldCaptureUrl(url) && shouldCaptureMethod(method)) {
        const t0 = performance.now();

        xhr.addEventListener('load', function () {
          try {
            if (xhr.status >= 200 && xhr.status < 300) {
              const contentType = xhr.getResponseHeader('Content-Type') || '';
              if (!shouldCaptureContentType(contentType)) return;

              const data = JSON.parse(xhr.responseText);
              const overhead = performance.now() - t0;
              recordPerf('xhr-intercept', url, overhead);
              const key = buildKey(url);
              saveToCache(key, data, { url, method, status: xhr.status });
            }
          } catch (err) {
            // 캐시 로직 에러 — XHR 응답에 영향 없음
            console.warn('[CopilotNetworkHook] XHR 캐시 에러 (격리됨):', err.message);
          }
        });
      }
    } catch (err) {
      console.warn('[CopilotNetworkHook] XHR send 래핑 에러 (격리됨):', err.message);
    }

    return originalSend.apply(this, args);
  };

  console.log('[CopilotNetworkHook] XHR override 완료 (에러 격리)');

  // ─── 메뉴 변경 감지 ───

  let currentMenu = location.pathname;

  function onMenuChange(newPath) {
    const prevMenu = currentMenu;
    currentMenu = newPath;
    if (prevMenu === currentMenu) return;

    console.log(`[CopilotNetworkHook] 메뉴 변경: ${prevMenu} → ${currentMenu}`);

    cache.deleteByMenu(prevMenu)
      .then((deleted) => {
        console.log(`[CopilotNetworkHook] 이전 메뉴 데이터 삭제: ${prevMenu} (${deleted}건)`);
      })
      .catch((err) => {
        console.warn('[CopilotNetworkHook] 메뉴 데이터 삭제 실패 (격리됨):', err.message);
      });
  }

  window.addEventListener('popstate', () => {
    try { onMenuChange(location.pathname); } catch { /* 격리 */ }
  });

  const originalPushState = history.pushState;
  history.pushState = function (...args) {
    const result = originalPushState.apply(this, args);
    try { onMenuChange(location.pathname); } catch { /* 격리 */ }
    return result;
  };

  const originalReplaceState = history.replaceState;
  history.replaceState = function (...args) {
    const result = originalReplaceState.apply(this, args);
    try { onMenuChange(location.pathname); } catch { /* 격리 */ }
    return result;
  };

  console.log('[CopilotNetworkHook] 메뉴 변경 감지 설정 완료');

  // ─── Public API ───

  window.CopilotNetworkHook = {
    isActive: true,
    FILTER,
    currentMenu: () => currentMenu,
    shouldCaptureUrl,
    shouldCaptureMethod,
    shouldCaptureContentType,
    buildKey,
    // 성능 측정
    getPerfLog,
    clearPerfLog,
    // 테스트용
    simulateMenuChange: (path) => {
      history.pushState(null, '', path);
    },
  };
})();
