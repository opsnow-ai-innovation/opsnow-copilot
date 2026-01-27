# `getAxios()` 미사용 — 직접 `axios.create()` 파일 목록

> com-cm-foweb(React) 프론트엔드에서 공통 라이브러리(`getAxios()`)를 사용하지 않고
> 직접 `axios.create()`로 인스턴스를 생성하는 파일 전체 목록

---

## 요약

| 구분 | 파일 수 | 인스턴스 수 |
|------|:-------:|:----------:|
| 패턴 B: API 모듈 직접 생성 | 11 | 14 |
| 패턴 C: 컴포넌트 직접 생성 | 12 | 12 |
| **합계** | **23** | **26** |

> 참고: `getAxios()` 경유 파일은 ~18개 (패턴 A). 전체 Axios 사용 파일은 ~41개.

---

## 패턴 B: API 모듈 직접 생성 (11개 파일, 14개 인스턴스)

### B-1. `client.js` — 팩토리 함수 3개

**파일**: `src/service/api/client.js`

| 라인 | 함수명 | timeout | baseURL | 기술적 필연 |
|:----:|--------|:-------:|---------|:-----------:|
| 79 | `createApiClient(prefix, timeout)` | 60초 (기본) | 동적 — request interceptor에서 `getApiUrl() + prefix` | O — 동적 baseURL |
| 116 | `createLongApiClient(prefix, timeout)` | 120초 | 동적 — `getLongApiUrl() + prefix` | **O** — API GW 30초 우회 |
| 164 | `createCustomApiClient(baseURL, timeout)` | 60초 (기본) | 정적 — 파라미터로 전달 | O — 커스텀 baseURL |

```javascript
// client.js:79
export const createApiClient = (prefix, timeout = API_TIMEOUTS.DEFAULT) => {
  const instance = axios.create({
    timeout,
    headers: { 'Content-Type': 'application/json' },
  });
  // request interceptor: config.baseURL = getApiUrl() + API_PREFIXES[prefix]
  // request interceptor: Authorization = Bearer {token}
```

---

### B-2. `longApiClient.js` — Long-Running API 전용

**파일**: `src/service/api/longApiClient.js:14`

| timeout | baseURL | 기술적 필연 |
|:-------:|---------|:-----------:|
| 120초 | 동적 — `getLongApiUrl() + API_PREFIXES.ASSET` | **O** — API GW 30초 우회, 별도 도메인 (`long-api.opsnow.com`) |

```javascript
const instance = axios.create({
  timeout: API_TIMEOUTS.LONG, // 120000ms
  headers: { 'Content-Type': 'application/json' },
});
// request interceptor: config.baseURL = getLongApiUrl() + API_PREFIXES.ASSET
```

---

### B-3. `consoleApi.js` — 외부 도메인 2개

**파일**: `src/service/api/console/consoleApi.js`

| 라인 | 변수명 | timeout | baseURL | 기술적 필연 |
|:----:|--------|:-------:|---------|:-----------:|
| 9 | `consoleClient` | 30초 | `TEMP_API_URL` (`https://api.opsnow.com`) | **O** — 외부 도메인 |
| 18 | `serviceClient` | 30초 | `https://service.opsnow.com` | **O** — 완전히 다른 서비스 |

```javascript
const consoleClient = axios.create({
  baseURL: TEMP_API_URL,              // https://api.opsnow.com
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

const serviceClient = axios.create({
  baseURL: 'https://service.opsnow.com',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});
```

---

### B-4. `insightApi.js` — Long-Running API

**파일**: `src/service/api/insight/insightApi.js:43`

| timeout | baseURL | 기술적 필연 |
|:-------:|---------|:-----------:|
| 120초 | 동적 — `getLongApiUrl()` | **O** — API GW 30초 우회 |

```javascript
const instance = axios.create({
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});
// request interceptor: config.baseURL = getLongApiUrl()
```

---

### B-5. `optimizationApi.js` — Optimization API

**파일**: `src/service/api/optimize/optimizationApi.js:11`

| timeout | baseURL | response transform | 기술적 필연 |
|:-------:|---------|:------------------:|:-----------:|
| 30초 | 동적 — `getApiUrl() + '/asset'` | `response.data` 자동 추출 | X — timeout, response transform |

```javascript
const createOptimizationApiClient = (timeout = 30000) => {
  const instance = axios.create({
    timeout,
    headers: { 'Content-Type': 'application/json' },
  });
  // request interceptor: config.baseURL = getApiUrl() + '/asset'
  // response interceptor: return response.data
```

---

### B-6. `rightSizingApi.js` — RightSizing API

**파일**: `src/service/api/optimize/rightSizingApi.js:11`

| timeout | baseURL | response transform | 기술적 필연 |
|:-------:|---------|:------------------:|:-----------:|
| 30초 | 동적 — `getApiUrl() + '/asset'` | `response.data` 자동 추출 | X — timeout, response transform |

```javascript
const createRightSizingApiClient = (timeout = 30000) => {
  const instance = axios.create({
    timeout,
    headers: { 'Content-Type': 'application/json' },
  });
  // request interceptor: config.baseURL = getApiUrl() + '/asset'
  // response interceptor: return response.data
```

---

### B-7. `usageApi.js` — Usage Monitor API

**파일**: `src/service/api/monitor/usageApi.js:11`

| timeout | baseURL | response transform | 기술적 필연 |
|:-------:|---------|:------------------:|:-----------:|
| 30초 | **요청별 동적** — 메서드 내에서 URL 직접 지정 | `response.data` 자동 추출 | X — timeout, response transform |

```javascript
const createUsageApiClient = (timeout = 30000) => {
  const instance = axios.create({
    timeout,
    headers: { 'Content-Type': 'application/json' },
  });
  // request interceptor: Authorization만 주입 (baseURL 없음)
  // response interceptor: return response.data
  // 각 메서드에서 전체 URL 직접 사용: instance.get(getUrls().usage + '/path')
```

---

### B-8. `companyApi.js` — Settings Company API

**파일**: `src/service/api/settings/companyApi.js:7`

| timeout | baseURL | 기술적 필연 |
|:-------:|---------|:-----------:|
| 60초 | 동적 — request interceptor에서 `getApiUrl()` | X — `getAxios()`로 대체 가능 |

```javascript
const settingsApiClient = axios.create({
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});
settingsApiClient.interceptors.request.use(config => {
  config.baseURL = getApiUrl();
  // Authorization = Bearer {token}
});
```

---

### B-9. `userApi.js` — Settings User API

**파일**: `src/service/api/settings/userApi.js:6`

| timeout | baseURL | 기술적 필연 |
|:-------:|---------|:-----------:|
| 60초 | 동적 — request interceptor에서 `getApiUrl()` | X — `companyApi.js`와 동일 패턴 복붙 |

```javascript
const settingsApiClient = axios.create({
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});
settingsApiClient.interceptors.request.use(config => {
  config.baseURL = getApiUrl();
  // Authorization = Bearer {token}
});
```

---

### B-10. `notificationsApi.js` — Notifications API (임시)

**파일**: `src/service/api/settings/notificationsApi.js:8`

| timeout | baseURL | 기술적 필연 |
|:-------:|---------|:-----------:|
| 30초 | **하드코딩** — `NOTIFICATIONS_BASE_URL` (`https://api.opsnow.com/platform/v1/plat`) | X — `TEMP_` 접두어 사용, 테스트 코드 |

```javascript
const notificationsClient = axios.create({
  baseURL: NOTIFICATIONS_BASE_URL,    // 하드코딩된 테스트 URL
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});
// 인증도 TEMP_AUTH_TOKEN 하드코딩 사용
```

---

### B-11. `tagManagerApi.js` — Tag Manager Govern API

**파일**: `src/service/api/govern/tagManagerApi.js:18`

| timeout | baseURL | 기술적 필연 |
|:-------:|---------|:-----------:|
| 30초 | 동적 — request interceptor에서 `getApiUrl()` | X — timeout만 다름 |

```javascript
const governApiClient = axios.create({
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});
governApiClient.interceptors.request.use(config => {
  config.baseURL = getApiUrl();
  // Authorization = Bearer {token}
});
```

---

## 패턴 C: 컴포넌트 직접 생성 (12개 파일, 전부 동일 패턴)

**모든 파일이 아래와 완전히 동일한 코드를 복붙하여 사용:**

```javascript
const tempApiClient = axios.create({
  baseURL: getAssetApiUrl(),
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

tempApiClient.interceptors.request.use(
  config => {
    const token = getStoreState()?.common?.authToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);
```

| 설정 | 값 |
|------|-----|
| timeout | 30초 |
| baseURL | `getAssetApiUrl()` (정적, 로드 시 결정) |
| 인증 | `getStoreState()?.common?.authToken` |
| 기술적 필연 | **X** — 전부 동일한 코드 복붙, 안티패턴 |

### 파일 목록

| # | 파일 경로 | 라인 |
|:-:|----------|:----:|
| 1 | `src/pages/v1.5/optimize/optimization/unused-resource/UnusedResource.jsx` | 22 |
| 2 | `src/pages/v1.5/optimize/optimization/settings/Settings.jsx` | 15 |
| 3 | `src/pages/v1.5/optimize/optimization/settings/tabs/RightSizingEC2.jsx` | 19 |
| 4 | `src/pages/v1.5/optimize/optimization/settings/tabs/RightSizingAzureVM.jsx` | 19 |
| 5 | `src/pages/v1.5/optimize/optimization/settings/tabs/RightSizingGCPVM.jsx` | 19 |
| 6 | `src/pages/v1.5/optimize/optimization/settings/tabs/RightSizingRDS.jsx` | 19 |
| 7 | `src/pages/v1.5/optimize/optimization/settings/tabs/RightSizingServerInstance.jsx` | 19 |
| 8 | `src/pages/v1.5/optimize/optimization/settings/tabs/UnusedResourceAWS.jsx` | 16 |
| 9 | `src/pages/v1.5/optimize/optimization/settings/tabs/UnusedResourceAzure.jsx` | 16 |
| 10 | `src/pages/v1.5/optimize/optimization/settings/tabs/UnusedResourceGCP.jsx` | 16 |
| 11 | `src/pages/v1.5/optimize/optimization/settings/tabs/UnusedResourceNCP.jsx` | 16 |
| 12 | `src/pages/v1.5/optimize/optimization/settings/tabs/ExclusionFromRecommendation.jsx` | 14 |

---

## 기술적 필연 여부 요약

### 기술적으로 `getAxios()` 사용 불가 — 4개 파일 (6개 인스턴스)

| 파일 | 사유 |
|------|------|
| `client.js` (createLongApiClient) | `getLongApiUrl()` — API GW 30초 타임아웃 우회, 별도 도메인 |
| `longApiClient.js` | `getLongApiUrl()` — API GW 30초 타임아웃 우회, 별도 도메인 |
| `consoleApi.js` (2개 인스턴스) | `api.opsnow.com`, `service.opsnow.com` — 완전히 다른 외부 서비스 |
| `insightApi.js` | `getLongApiUrl()` — API GW 30초 타임아웃 우회 |

### 코드 비일관성 — 19개 파일 (20개 인스턴스)

| 구분 | 파일 수 | 사유 |
|------|:-------:|------|
| timeout/response transform만 다름 | 4 | `optimizationApi`, `rightSizingApi`, `usageApi`, `tagManagerApi` |
| 동일 설정 복붙 | 2 | `companyApi`, `userApi` |
| 임시 코드 | 1 | `notificationsApi` (TEMP_ 접두어) |
| 컴포넌트 내 동일 코드 복붙 | 12 | Optimization settings 탭 전부 |

---

## 참고: common-io-web (Vue)과의 비교

| 항목 | com-cm-foweb (React) | common-io-web (Vue) |
|------|:--------------------:|:-------------------:|
| 직접 `axios.create()` | **23개 파일, 26개 인스턴스** | **0개** |
| 공통 인스턴스 경유 | 18/41 (44%) | 53/53 (100%) |
| HTTP 클라이언트 통일성 | 비일관적 | **완전 통일** (`$finOpsAxios`) |
