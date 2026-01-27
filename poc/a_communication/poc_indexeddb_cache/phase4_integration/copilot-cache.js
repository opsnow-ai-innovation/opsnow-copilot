/**
 * Copilot Cache — IndexedDB CRUD + 관리 정책 + 에러 격리
 *
 * Phase 4: Phase 3 최종 버전 그대로 사용
 *          모든 경로 try-catch 격리, DB 장애 시에도 호출자에게 에러 전파 없음
 *
 * DB: copilot-cache
 * Store: api-responses
 */

const DB_NAME = 'copilot-cache';
const STORE_NAME = 'api-responses';
const DB_VERSION = 1;

// ─── 관리 정책 설정 ───
const POLICY = {
  TTL: 5 * 60 * 1000,          // 5분 (PoC용 짧은 TTL)
  MAX_ENTRIES: 100,             // 최대 저장 건수
  MAX_SIZE_BYTES: 100 * 1024 * 1024, // 단일 응답 최대 크기 (100MB)
  DEDUP_INTERVAL: 1000,         // 중복 방지 간격 (1초)
};

let dbInstance = null;

// ─── 테스트용: 강제 에러 모드 ───
let _forceError = false;

function setForceError(enabled) {
  _forceError = enabled;
  console.log(`[CopilotCache] 강제 에러 모드: ${enabled ? 'ON' : 'OFF'}`);
}

// 중복 방지용 최근 저장 기록 { key: timestamp }
const recentSaves = new Map();

/**
 * IndexedDB 열기 (싱글턴)
 */
function openDB() {
  if (_forceError) return Promise.reject(new Error('[Test] 강제 DB 에러'));
  if (dbInstance) return Promise.resolve(dbInstance);

  return new Promise((resolve, reject) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'key' });
          store.createIndex('menu', 'menu', { unique: false });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };

      request.onsuccess = (event) => {
        dbInstance = event.target.result;
        resolve(dbInstance);
      };

      request.onerror = (event) => {
        reject(event.target.error);
      };
    } catch (err) {
      reject(err);
    }
  });
}

// ─── 중복 방지 ───

function isDuplicate(key) {
  const lastSave = recentSaves.get(key);
  if (lastSave && Date.now() - lastSave < POLICY.DEDUP_INTERVAL) {
    return true;
  }
  recentSaves.set(key, Date.now());
  return false;
}

// ─── 크기 체크 ───

function isOversized(data) {
  try {
    const size = new Blob([JSON.stringify(data)]).size;
    return size > POLICY.MAX_SIZE_BYTES;
  } catch {
    return false;
  }
}

function getDataSize(data) {
  try {
    return new Blob([JSON.stringify(data)]).size;
  } catch {
    return 0;
  }
}

// ─── TTL 관리 ───

async function evictExpired() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const index = store.index('timestamp');
    const cutoff = Date.now() - POLICY.TTL;
    const range = IDBKeyRange.upperBound(cutoff);
    const request = index.openCursor(range);
    let deleted = 0;

    request.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor) {
        cursor.delete();
        deleted++;
        cursor.continue();
      } else {
        resolve(deleted);
      }
    };

    request.onerror = (event) => reject(event.target.error);
  });
}

// ─── 용량 관리 ───

async function evictOldest() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const countReq = store.count();

    countReq.onsuccess = () => {
      const count = countReq.result;
      if (count <= POLICY.MAX_ENTRIES) {
        resolve(0);
        return;
      }

      const toDelete = count - POLICY.MAX_ENTRIES;
      const index = store.index('timestamp');
      const cursorReq = index.openCursor();
      let deleted = 0;

      cursorReq.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor && deleted < toDelete) {
          cursor.delete();
          deleted++;
          cursor.continue();
        } else {
          resolve(deleted);
        }
      };

      cursorReq.onerror = (event) => reject(event.target.error);
    };

    countReq.onerror = (event) => reject(event.target.error);
  });
}

// ─── CRUD (에러 격리) ───

/**
 * API 응답 저장 — 에러 격리: 실패해도 null 반환, 예외 전파 없음
 */
async function put(key, data, meta = {}) {
  try {
    if (isDuplicate(key)) {
      console.log('[CopilotCache] 중복 스킵:', key);
      return null;
    }

    if (isOversized(data)) {
      console.log('[CopilotCache] 크기 초과 스킵:', key, getDataSize(data), 'bytes');
      return null;
    }

    await evictExpired().catch(() => {});
    await evictOldest().catch(() => {});

    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);

        const record = {
          key,
          data,
          url: meta.url || key,
          method: meta.method || 'GET',
          status: meta.status || 200,
          menu: meta.menu || location.pathname,
          size: getDataSize(data),
          timestamp: Date.now(),
        };

        const request = store.put(record);
        request.onsuccess = () => resolve(record);
        request.onerror = (event) => {
          console.warn('[CopilotCache] put 실패:', event.target.error);
          resolve(null);
        };
      } catch (err) {
        console.warn('[CopilotCache] put 트랜잭션 에러:', err);
        resolve(null);
      }
    });
  } catch (err) {
    console.warn('[CopilotCache] put 에러 (격리됨):', err.message);
    return null;
  }
}

/**
 * 키로 데이터 조회 — 에러 격리
 */
async function get(key) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.get(key);

        request.onsuccess = () => {
          const record = request.result;
          if (!record) { resolve(null); return; }

          if (Date.now() - record.timestamp > POLICY.TTL) {
            store.delete(key);
            console.log('[CopilotCache] TTL 만료 삭제:', key);
            resolve(null);
            return;
          }

          resolve(record);
        };

        request.onerror = () => resolve(null);
      } catch {
        resolve(null);
      }
    });
  } catch (err) {
    console.warn('[CopilotCache] get 에러 (격리됨):', err.message);
    return null;
  }
}

async function getAllKeys() {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.getAllKeys();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => resolve([]);
      } catch {
        resolve([]);
      }
    });
  } catch {
    return [];
  }
}

async function getAll() {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => resolve([]);
      } catch {
        resolve([]);
      }
    });
  } catch {
    return [];
  }
}

async function remove(key) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.delete(key);
        request.onsuccess = () => resolve();
        request.onerror = () => resolve();
      } catch {
        resolve();
      }
    });
  } catch {
    // 격리
  }
}

async function clear() {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.clear();
        request.onsuccess = () => resolve();
        request.onerror = () => resolve();
      } catch {
        resolve();
      }
    });
  } catch {
    // 격리
  }
}

async function getByMenu(menu) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const index = store.index('menu');
        const request = index.getAll(menu);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => resolve([]);
      } catch {
        resolve([]);
      }
    });
  } catch {
    return [];
  }
}

async function deleteByMenu(menu) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const index = store.index('menu');
        const request = index.openCursor(menu);
        let deleted = 0;

        request.onsuccess = (event) => {
          const cursor = event.target.result;
          if (cursor) {
            cursor.delete();
            deleted++;
            cursor.continue();
          } else {
            resolve(deleted);
          }
        };

        request.onerror = () => resolve(0);
      } catch {
        resolve(0);
      }
    });
  } catch {
    return 0;
  }
}

async function count() {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.count();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => resolve(0);
      } catch {
        resolve(0);
      }
    });
  } catch {
    return 0;
  }
}

// Public API
window.CopilotCache = {
  POLICY,
  openDB,
  put,
  get,
  getAll,
  getAllKeys,
  remove,
  clear,
  count,
  getByMenu,
  deleteByMenu,
  evictExpired,
  evictOldest,
  isDuplicate,
  isOversized,
  getDataSize,
  // Phase 3 테스트용
  setForceError,
};
