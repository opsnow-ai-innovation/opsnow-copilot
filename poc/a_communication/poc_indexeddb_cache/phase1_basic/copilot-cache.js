/**
 * Copilot Cache — IndexedDB CRUD 모듈
 *
 * DB: copilot-cache
 * Store: api-responses
 * Key: URL (또는 URL + params 조합)
 */

const DB_NAME = 'copilot-cache';
const STORE_NAME = 'api-responses';
const DB_VERSION = 1;

let dbInstance = null;

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

/**
 * API 응답 저장
 * @param {string} key - 저장 키 (URL 또는 URL + params)
 * @param {*} data - 응답 데이터
 * @param {object} meta - 메타 정보 { url, method, status, menu }
 */
async function put(key, data, meta = {}) {
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
      timestamp: Date.now(),
    };

    const request = store.put(record);
    request.onsuccess = () => resolve(record);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 키로 데이터 조회
 * @param {string} key
 * @returns {Promise<object|null>}
 */
async function get(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.get(key);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * 저장된 모든 키 목록 조회
 * @returns {Promise<string[]>}
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
 * @returns {Promise<object[]>}
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
 * @param {string} key
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
 * @param {string} menu - location.pathname
 * @returns {Promise<object[]>}
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
 * @param {string} menu - location.pathname
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

// Public API
window.CopilotCache = {
  openDB,
  put,
  get,
  getAll,
  getAllKeys,
  remove,
  clear,
  getByMenu,
  deleteByMenu,
};
