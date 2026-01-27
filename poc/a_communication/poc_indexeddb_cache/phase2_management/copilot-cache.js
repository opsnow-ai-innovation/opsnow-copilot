/**
 * Copilot Cache — IndexedDB CRUD + 관리 정책
 *
 * Phase 2: TTL, 용량 상한, 중복 방지, 메뉴별 삭제 정책 추가
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
  MAX_SIZE_BYTES: 100 * 1024 * 1024, // 단일 응답 최대 크기 (100MB, 사실상 무제한)
  DEDUP_INTERVAL: 1000,         // 중복 방지 간격 (1초)
};

let dbInstance = null;

// 중복 방지용 최근 저장 기록 { key: timestamp }
const recentSaves = new Map();

/**
 * IndexedDB 열기 (싱글턴)
 */
function openDB() {
  if (dbInstance) return Promise.resolve(dbInstance);

  return new Promise((resolve, reject) => {
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
  });
}

// ─── 중복 방지 ───

/**
 * 짧은 시간 내 동일 키 저장 요청인지 확인
 * @param {string} key
 * @returns {boolean} true이면 중복 → 스킵해야 함
 */
function isDuplicate(key) {
  const lastSave = recentSaves.get(key);
  if (lastSave && Date.now() - lastSave < POLICY.DEDUP_INTERVAL) {
    return true;
  }
  recentSaves.set(key, Date.now());
  return false;
}

// ─── 크기 체크 ───

/**
 * 데이터 크기가 상한을 초과하는지 확인
 * @param {*} data
 * @returns {boolean} true이면 초과 → 스킵해야 함
 */
function isOversized(data) {
  try {
    const size = new Blob([JSON.stringify(data)]).size;
    return size > POLICY.MAX_SIZE_BYTES;
  } catch {
    return false;
  }
}

/**
 * 데이터 크기 (bytes) 반환
 * @param {*} data
 * @returns {number}
 */
function getDataSize(data) {
  try {
    return new Blob([JSON.stringify(data)]).size;
  } catch {
    return 0;
  }
}

// ─── TTL 관리 ───

/**
 * 만료된 레코드 정리
 * @returns {Promise<number>} 삭제된 건수
 */
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

/**
 * 저장 건수가 상한을 초과하면 오래된 항목부터 제거
 * @returns {Promise<number>} 삭제된 건수
 */
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

      // 오래된 순으로 초과분 삭제
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

// ─── CRUD ───

/**
 * API 응답 저장 (관리 정책 적용)
 * @param {string} key
 * @param {*} data
 * @param {object} meta - { url, method, status, menu }
 * @returns {Promise<object|null>} 저장된 레코드 또는 null(스킵)
 */
async function put(key, data, meta = {}) {
  // 중복 방지
  if (isDuplicate(key)) {
    console.log('[CopilotCache] 중복 스킵:', key);
    return null;
  }

  // 크기 초과 스킵
  if (isOversized(data)) {
    console.log('[CopilotCache] 크기 초과 스킵:', key, getDataSize(data), 'bytes');
    return null;
  }

  // TTL 만료 정리
  await evictExpired().catch(() => {});

  // 용량 초과 정리
  await evictOldest().catch(() => {});

  const db = await openDB();
  return new Promise((resolve, reject) => {
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
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 키로 데이터 조회 (TTL 만료 체크 포함)
 * @param {string} key
 * @returns {Promise<object|null>}
 */
async function get(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const request = store.get(key);

    request.onsuccess = () => {
      const record = request.result;
      if (!record) {
        resolve(null);
        return;
      }

      // TTL 만료 체크
      if (Date.now() - record.timestamp > POLICY.TTL) {
        store.delete(key);
        console.log('[CopilotCache] TTL 만료 삭제:', key);
        resolve(null);
        return;
      }

      resolve(record);
    };

    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 저장된 모든 키 목록 조회
 */
async function getAllKeys() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.getAllKeys();
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 저장된 모든 레코드 조회
 */
async function getAll() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 키로 데이터 삭제
 */
async function remove(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const request = store.delete(key);
    request.onsuccess = () => resolve();
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 전체 데이터 삭제
 */
async function clear() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const request = store.clear();
    request.onsuccess = () => resolve();
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 메뉴별 데이터 조회
 * @param {string} menu
 */
async function getByMenu(menu) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const index = store.index('menu');
    const request = index.getAll(menu);
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 메뉴별 데이터 삭제
 * @param {string} menu
 * @returns {Promise<number>} 삭제 건수
 */
async function deleteByMenu(menu) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
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

    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 저장 건수 조회
 */
async function count() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.count();
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
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
};
