/**
 * Copilot Network Hook — fetch + XHR 오버라이드 + 필터링 + 메뉴 변경 감지
 *
 * Phase 2: URL/메서드/Content-Type/크기 필터링, 메뉴 변경 시 이전 데이터 삭제
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
    // 저장 대상 URL 패턴 (포함)
    urlPatterns: ['/api/'],

    // 저장 제외 URL 패턴
    excludePatterns: ['/auth/', '/login/', '/logout/', '/health'],

    // 저장 대상 HTTP 메서드
    methods: ['GET', 'POST'],

    // 저장 대상 Content-Type
    contentTypes: ['application/json'],
  };

  // ─── 필터링 유틸 ───

  /**
   * URL이 저장 대상인지 판별
   */
  function shouldCaptureUrl(url) {
    try {
      const parsed = new URL(url, location.origin);
      const path = parsed.pathname;

      // 제외 패턴 먼저 체크
      if (FILTER.excludePatterns.some((p) => path.includes(p))) return false;

      // 포함 패턴 체크
      return FILTER.urlPatterns.some((p) => path.includes(p));
    } catch {
      return false;
    }
  }

  /**
   * HTTP 메서드가 저장 대상인지 판별
   */
  function shouldCaptureMethod(method) {
    return FILTER.methods.includes(method.toUpperCase());
  }

  /**
   * Content-Type이 저장 대상인지 판별
   */
  function shouldCaptureContentType(contentType) {
    if (!contentType) return false;
    return FILTER.contentTypes.some((ct) => contentType.includes(ct));
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
   * fire-and-forget 저장
   */
  function saveToCache(key, data, meta) {
    try {
      cache.put(key, data, meta).then((result) => {
        if (result) {
          console.log(`[CopilotNetworkHook] 저장: ${key} (${cache.getDataSize(data)} bytes)`);
        }
      }).catch((err) => {
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

    // 메서드 필터링
    if (!shouldCaptureMethod(method)) {
      return originalFetch.apply(this, args);
    }

    return originalFetch.apply(this, args).then((response) => {
      if (!shouldCaptureUrl(url)) return response;
      if (!response.ok) return response;

      // Content-Type 필터링
      const contentType = response.headers.get('Content-Type') || '';
      if (!shouldCaptureContentType(contentType)) return response;

      // clone()으로 원본 보존
      const cloned = response.clone();
      cloned
        .json()
        .then((data) => {
          // 크기 체크는 cache.put() 내부에서 처리
          const key = buildKey(url);
          saveToCache(key, data, { url, method, status: response.status });
        })
        .catch(() => {
          // JSON 파싱 실패 — 스킵
        });

      return response;
    });
  };

  console.log('[CopilotNetworkHook] fetch override 완료');

  // ─── XHR Override ───

  const OriginalXHR = window.XMLHttpRequest;
  const originalOpen = OriginalXHR.prototype.open;
  const originalSend = OriginalXHR.prototype.send;

  OriginalXHR.prototype.open = function (method, url, ...rest) {
    this._copilot = { method, url };
    return originalOpen.call(this, method, url, ...rest);
  };

  OriginalXHR.prototype.send = function (...args) {
    const xhr = this;
    const { method, url } = xhr._copilot || {};

    if (url && shouldCaptureUrl(url) && shouldCaptureMethod(method)) {
      xhr.addEventListener('load', function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          // Content-Type 필터링
          const contentType = xhr.getResponseHeader('Content-Type') || '';
          if (!shouldCaptureContentType(contentType)) return;

          try {
            const data = JSON.parse(xhr.responseText);
            const key = buildKey(url);
            saveToCache(key, data, { url, method, status: xhr.status });
          } catch {
            // JSON 파싱 실패 — 스킵
          }
        }
      });
    }

    return originalSend.apply(this, args);
  };

  console.log('[CopilotNetworkHook] XHR override 완료');

  // ─── 메뉴 변경 감지 (SPA History API 래핑) ───

  let currentMenu = location.pathname;

  function onMenuChange(newPath) {
    const prevMenu = currentMenu;
    currentMenu = newPath;

    if (prevMenu === currentMenu) return;

    console.log(`[CopilotNetworkHook] 메뉴 변경: ${prevMenu} → ${currentMenu}`);

    // 이전 메뉴 데이터 삭제 (fire-and-forget)
    cache
      .deleteByMenu(prevMenu)
      .then((deleted) => {
        console.log(`[CopilotNetworkHook] 이전 메뉴 데이터 삭제: ${prevMenu} (${deleted}건)`);
      })
      .catch((err) => {
        console.warn('[CopilotNetworkHook] 메뉴 데이터 삭제 실패:', err);
      });
  }

  // popstate (뒤로가기/앞으로가기)
  window.addEventListener('popstate', () => {
    onMenuChange(location.pathname);
  });

  // pushState 래핑
  const originalPushState = history.pushState;
  history.pushState = function (...args) {
    const result = originalPushState.apply(this, args);
    onMenuChange(location.pathname);
    return result;
  };

  // replaceState 래핑
  const originalReplaceState = history.replaceState;
  history.replaceState = function (...args) {
    const result = originalReplaceState.apply(this, args);
    onMenuChange(location.pathname);
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
    // 테스트용: 메뉴 변경 시뮬레이션
    simulateMenuChange: (path) => {
      history.pushState(null, '', path);
    },
  };
})();
