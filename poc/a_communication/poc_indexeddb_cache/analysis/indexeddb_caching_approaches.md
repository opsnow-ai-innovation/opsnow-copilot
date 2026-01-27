# API 응답 → IndexedDB 저장 방식 비교

> OpsNow 프론트엔드(com-cm-foweb)에 IndexedDB 캐싱을 도입하기 위한 방식별 분석

---

## 전제 조건

| 항목 | 현재 상태 |
|------|----------|
| HTTP 클라이언트 | Axios (팩토리 패턴, `client.js`) |
| 데이터 페칭 | React Query (TanStack Query v5) |
| 상태 관리 | Redux Toolkit |
| 기존 IndexedDB 사용 | 없음 |
| 빌드 도구 | Vite |
| 핵심 요구 | **페이지 최초 렌더링 시 API 응답이 IndexedDB에 저장되어야 함** |

---

## OpsNow Axios 인스턴스 현황 (코드 분석 결과)

방식별 분석에 앞서, OpsNow 프론트엔드의 Axios 사용 구조를 먼저 정리한다.
**이 구조가 방식 선택에 결정적 영향을 미친다.**

### Axios 인스턴스가 3가지 패턴으로 분산되어 있음

```
OpsNow 프론트엔드 Axios 구조:

패턴 A: getAxios() 공통 라이브러리 (~18개 파일)
  └── @opsnow-common/opsnow-finops-common-axios
      └── 단일 인스턴스 (싱글턴)
      └── 사용: /src/service/*Service.js, /src/services/*/

패턴 B: client.js 팩토리 직접 axios.create() (~11개 API 파일)
  └── createApiClient(), createLongApiClient(), createCustomApiClient()
  └── 사용: settings, optimization, monitor, console, govern 등

패턴 C: 페이지 컴포넌트 내 직접 axios.create() (~12개 파일)
  └── 사용: /src/pages/v1.5/optimize/optimization/settings/tabs/*.jsx
```

### 인스턴스별 상세

| 패턴 | 파일 수 | `getAxios()` 경유 | 예시 |
|------|---------|-------------------|------|
| A. 공통 라이브러리 | ~18 | O | `billingService.js`, `anomaliesService.js` |
| B. client.js 팩토리 | ~11 | **X** | `companyApi.js`, `usageApi.js`, `consoleApi.js` |
| C. 컴포넌트 직접 생성 | ~12 | **X** | `RightSizingEC2.jsx`, `UnusedResource.jsx` |
| **합계** | **~41** | | |

### 왜 `getAxios()`를 안 쓰고 따로 만드는가?

| 이유 | 해당 파일 | 기술적 필연성 |
|------|----------|-------------|
| 다른 도메인 사용 (`getLongApiUrl()`) | `longApiClient.js` | **있음** - API Gateway 30초 타임아웃 우회 |
| 외부 도메인 직접 지정 | `consoleApi.js` (`api.opsnow.com`, `service.opsnow.com`) | **있음** - 완전히 다른 서비스 |
| 타임아웃만 다름 (30초) | `usageApi.js`, `rightSizingApi.js` | 없음 - 파라미터로 해결 가능 |
| 동일한 설정 복붙 | `companyApi.js`, `userApi.js` | 없음 - `getAxios()` 사용 가능 |
| 임시 코드 | `notificationsApi.js` (`TEMP_` 접두어) | 없음 - 레거시 |
| 컴포넌트 내 직접 생성 | `RightSizingEC2.jsx` 등 12개 | 없음 - 안티패턴 |

**결론: 기술적 필연은 2~3개 파일뿐이고, 나머지는 코드 관리 비일관성이다.**
단기간에 정리될 구조가 아니므로, 이 현실을 전제로 방식을 선택해야 한다.

### Axios 어댑터 분석 (공통 라이브러리 소스 확인)

Axios는 `adapter` 설정에 따라 브라우저에서 `XMLHttpRequest(xhr)` 또는 `fetch`를 사용한다.
**이 설정이 방식 5 (fetch override)의 실효성을 좌우한다.**

#### 공통 라이브러리 의존성 체인

```
com-cm-foweb (프론트엔드 앱)
  └── @opsnow-common/opsnow-finops-common-ui-loader
        ├── axios: "^1.7.2"  (devDependency)         ← 실제 설치 버전 결정
        └── @opsnow-common/opsnow-finops-common-axios
              ├── axios: "^1.6.8"  (dependency)
              └── lib/main.js:71-75 Axios 인스턴스 생성:
                    axios.create({
                      baseURL: '/',
                      headers: resultHeaders,
                      timeout,
                    })
                    // adapter 설정 없음 → Axios 기본값 사용
```

#### Axios 기본 어댑터 동작 (adapter 미설정 시)

```javascript
// Axios 1.7+ 내부 기본값
defaults.adapter = ['xhr', 'fetch'];
// → 배열 순서대로 시도: xhr이 사용 가능하면 xhr 사용, 아니면 fetch
// → 브라우저에서는 XMLHttpRequest가 항상 사용 가능하므로 xhr이 선택됨
```

| Axios 버전 | adapter 미설정 시 브라우저 기본 | 비고 |
|-----------|-------------------------------|------|
| ~1.6.x | XMLHttpRequest (xhr) | fetch 어댑터 없음 |
| 1.7.0+ | **xhr 우선** (`['xhr', 'fetch']`) | xhr 사용 가능하면 xhr 선택 |

#### OpsNow 전체 인스턴스의 adapter 상태

| 패턴 | adapter 명시 설정 | 실제 사용 어댑터 (추정) |
|------|-----------------|----------------------|
| A. 공통 라이브러리 (`getAxios()`) | 없음 | **xhr** (Axios 기본값) |
| B. client.js 팩토리 | 없음 | **xhr** (Axios 기본값) |
| C. 컴포넌트 직접 생성 | 없음 | **xhr** (Axios 기본값) |

**전체 41개 파일 어디에서도 `adapter` 옵션을 명시적으로 설정하지 않고 있다.**
**Axios 기본값이 xhr 우선이므로, `window.fetch` override만으로는 API 응답을 잡지 못할 가능성이 높다.**

> **주의**: 위는 Axios 소스 코드 분석 기반 추정이다. 실제 런타임에서 어떤 어댑터가
> 사용되는지는 PoC에서 반드시 확인해야 한다.

### `getAxios()` 통일 가능성 분석

모든 Axios 인스턴스를 `getAxios()`로 통일하면 interceptor 1곳에서 전체를 커버할 수 있을까?

#### `getAxios()`의 구조적 한계

```javascript
// opsnow-finops-common-axios/lib/main.js
let axiosInstance = null;  // ← 모듈 레벨 단일 변수

const initializeAxios = (config) => {
  if (axiosInstance) {
    console.error('이미 초기화되었습니다. getAxios()를 사용해주세요.');
    return;  // ← 재초기화 거부
  }
  axiosInstance = axios.create({
    baseURL: '/',       // ← 하드코딩, 파라미터 없음
    headers: resultHeaders,
    timeout,
  });
};
```

| 제약 | 상세 |
|------|------|
| **싱글턴** | 앱 전체에 인스턴스 1개만 존재. 설정이 다른 인스턴스 생성 불가 |
| **baseURL 고정** | `'/'`로 하드코딩. `initializeAxios()` 옵션에 baseURL 없음 |
| **timeout 1개** | 싱글턴이므로 60초/30초/120초를 동시에 사용할 수 없음 |
| **response transform 없음** | 일부 API는 `response.data` 자동 추출이 필요하나 지원하지 않음 |

#### 비-getAxios() 인스턴스들의 요구사항

| 필요 기능 | 해당 인스턴스 | getAxios() 지원 |
|----------|-------------|----------------|
| `getLongApiUrl()` baseURL | `longApiClient`, `insightApi` | **X** |
| `getAssetApiUrl()` baseURL | 컴포넌트 12개 | **X** |
| 외부 도메인 (`service.opsnow.com`) | `consoleApi` | **X** |
| timeout 30초 | `optimizationApi`, 컴포넌트들 | 동시 불가 |
| timeout 120초 | `longApiClient`, `insightApi` | 동시 불가 |
| `response.data` 자동 추출 | `optimizationApi`, `usageApi` 등 | **X** |

#### 통일하려면 공통 라이브러리 자체를 개편해야 함

```
필요한 변경:
  opsnow-finops-common-axios   — 싱글턴 → 팩토리 패턴 추가 (createAxios)
  opsnow-finops-common-ui-loader — 신규 API 노출
  com-cm-foweb 41개 파일        — import 변경 + 설정 마이그레이션
  + 다른 OpsNow 프로젝트들      — 호환성 확인
```

**Copilot IndexedDB를 위해 전사 공통 라이브러리를 개편하는 것은 목적 대비 비용이 과도하다.**

---

### 화면 데이터 Fetching 패턴 분석 (코드 분석 결과)

Copilot이 필요한 것은 "모든 API 응답"이 아니라
**"사용자가 현재 보고 있는 화면의 데이터를 만드는 API 응답"**이다.
이 관점에서 OpsNow 프론트엔드의 데이터 fetching 패턴을 분석한다.

#### 화면 데이터 출처 분포

```
OpsNow 화면 데이터 출처 (318개 페이지 컴포넌트 분석):

React Query (useQuery + custom hooks)  ───── ~70%
  ├── Credit (6 hooks)
  ├── FinOps KPIs (27 hooks)
  ├── Policy Management (14 hooks)
  ├── My Commitments (37+ hooks)
  └── CDN Dashboard (6 hooks)

Redux dispatch (createAsyncThunk)  ──────── ~15%
  └── Overview 페이지, 글로벌 상태

Manual axios (useState + useEffect)  ────── ~10%
  ├── Optimization Settings (12개 컴포넌트) ← Pattern C 전부
  ├── Resource Alert
  └── Usage Monitor

기타 혼합 패턴  ──────────────────────────── ~5%
```

#### Pattern C 컴포넌트: React Query 전혀 미사용 (확인 완료)

12개 파일 모두 동일한 패턴:

```javascript
// RightSizingEC2.jsx, UnusedResourceAWS.jsx 등 12개 전부
const tempApiClient = axios.create({ ... });    // 직접 인스턴스 생성
const [data, setData] = useState(null);          // useState로 상태 관리
useEffect(() => { fetchData(); }, [dep]);        // useEffect에서 직접 호출
const fetchData = async () => {
  const result = await tempApiClient.post(...);  // 직접 axios 호출
  setData(result);
};
// → useQuery 사용 0건. React Query를 완전히 우회.
```

#### 페이지별 데이터 fetching 패턴

| 페이지 영역 | 패턴 | React Query 경유 |
|------------|------|:---------------:|
| Credit | useQuery custom hooks (6개) | **O** |
| FinOps KPIs | useQuery custom hooks (27개) | **O** |
| Policy Management | useQuery custom hooks (14개) | **O** |
| My Commitments | useQuery custom hooks (37+개) | **O** |
| CDN Dashboard | useQuery custom hooks (6개) | **O** |
| **Overview** | Redux dispatch + manual axios | **X** |
| **Optimization Settings** | useState + useEffect + 직접 axios | **X** |
| **Usage Monitor** | useState + useEffect + 직접 axios | **X** |
| **Resource Alert** | useState + useCallback + 직접 axios | **X** |

#### 이 분포가 방식 선택에 미치는 영향

- **방식 4 (RQ Event)**: 화면 데이터의 **~70%만 커버**. Overview, Optimization, Usage, Resource Alert 페이지 누락.
- **방식 5 (Network Override)**: fetching 패턴과 무관하게 **100% 커버**.

---

### 이 구조가 방식 선택에 미치는 영향

- **방식 1 (Axios Interceptor)**: `client.js` 팩토리에만 걸면 패턴 A 일부 + 패턴 B만 커버. 패턴 C와 `getAxios()` 직접 사용 파일은 누락.
- **방식 5 (fetch Override만)**: Axios 기본 어댑터가 xhr이면 **어떤 패턴도 잡지 못할 수 있음**.
- **방식 5 확장 (fetch + XHR Override)**: `window.fetch`와 `XMLHttpRequest` 모두 오버라이드하면 어댑터와 무관하게 전체 커버 가능.

---

## 방식 1: Axios Response Interceptor

### 개요

기존 Axios 인스턴스의 response interceptor에 IndexedDB 저장 로직을 추가한다.

### 동작 흐름

```
useQuery → Axios request interceptor (토큰 주입)
         → xhr 또는 fetch
         → API Server
         → Response
         → Axios response interceptor (에러 처리)
         → [추가] IndexedDB 저장          ← 여기에 끼워넣기
         → React Query 캐시
         → 컴포넌트 렌더링
```

### 구현 예시

```javascript
// src/service/api/client.js (기존 파일 수정)

import { saveToCopilotCache } from '../copilot/indexeddb-cache';

// 기존 createApiClient() 함수 내부에 추가
instance.interceptors.response.use((response) => {
  const url = response.config.url;
  const cacheTargets = ['/cost/', '/asset/', '/billing/'];

  if (cacheTargets.some(prefix => url.startsWith(prefix))) {
    // 비동기로 저장 (응답 반환을 블로킹하지 않음)
    saveToCopilotCache({
      url,
      params: response.config.params,
      data: response.data,
      timestamp: Date.now()
    }).catch(() => {}); // 저장 실패해도 기존 흐름에 영향 없음
  }

  return response; // 기존 흐름 그대로
});
```

### 분석

| 항목 | 평가 |
|------|------|
| 수정 파일 | `client.js` 1개 + IndexedDB 유틸 파일 1개 추가 |
| 기존 코드 변경 | interceptor 추가만 (기존 로직 변경 없음) |
| 첫 방문 저장 보장 | **보장됨** - Axios 응답 경로에 있으므로 100% 실행 |
| 저장 대상 선별 | URL 패턴으로 필터링 가능 |
| 기존 기능 영향 | 없음 (response를 그대로 반환) |
| 에러 격리 | 저장 실패해도 catch로 무시 가능 |
| 프론트엔드 팀 협조 | **필요** (client.js 수정) |
| **API 커버리지** | **부분적 (~11/41 파일)** - client.js 팩토리 경유 인스턴스만 |

### 장점

- 가장 직관적이고 정석적인 방법
- Axios response 객체에서 URL, params, data를 바로 꺼낼 수 있어 저장이 용이
- 저장 실패가 기존 기능에 영향을 주지 않음

### 단점

- **OpsNow의 Axios 인스턴스가 21개+ 분산되어 있어, client.js 팩토리에만 걸면 전체를 커버하지 못함**
- 전체 커버를 위해서는 `getAxios()` 공통 라이브러리, 직접 생성 인스턴스, 컴포넌트 인스턴스 각각에 interceptor를 추가해야 함
- 공통 라이브러리(`@opsnow-common/opsnow-finops-common-axios`)는 외부 패키지이므로 수정이 어려움
- 리트라이 로직(공통 라이브러리 GET 최대 3회 재시도)으로 인해 동일 API에 대해 중복 저장 가능

### ⚠️ OpsNow 환경에서의 한계

```
client.js 팩토리 interceptor 커버리지:

  패턴 A (getAxios 공통 라이브러리)    → X (외부 패키지, 수정 불가)
  패턴 B (client.js 팩토리)           → O (여기에 interceptor 추가)
  패턴 B (직접 axios.create API 파일)  → X (별도 인스턴스)
  패턴 C (컴포넌트 직접 생성)          → X (별도 인스턴스)
```

**단독 사용 부적합: 전체 API의 약 1/4만 커버 가능**

---

## 방식 2: Service Worker → 탈락

### 개요

Service Worker가 브라우저의 fetch 이벤트를 가로채, 응답 사본을 IndexedDB에 저장한다.

### 탈락 사유

| 문제 | 설명 |
|------|------|
| 첫 방문 저장 불가 | SW는 비동기로 설치/활성화됨. 페이지 최초 API 호출 시점에 SW가 아직 활성화되지 않아 가로채지 못함 |
| `skipWaiting()` + `clients.claim()` 한계 | 설치→활성화 과정 자체가 비동기이므로, 앱이 먼저 API를 호출하면 누락 |
| Copilot 핵심 요구 미충족 | 사용자가 보고 있는 화면의 데이터가 바로 최초 렌더링 시 호출된 API 결과임 |
| 오프라인 지원 불필요 | Copilot은 WebSocket 서버 연결이 필수이므로, SW의 오프라인 캐시 장점이 무의미 |

**첫 방문은 최초 1회(보통 로그인 후 첫 페이지 진입)만 해당하며, 이후 메뉴 이동에서는 SW가 정상 동작한다. 그러나 이 최초 1회가 보장되지 않으면 Copilot 신뢰성에 문제가 생긴다.**

---

## 방식 3: React Query Persister Plugin → 부적합

### 개요

TanStack Query가 공식 제공하는 `persistQueryClient` 플러그인을 사용하여,
React Query의 인메모리 캐시 전체를 자동으로 IndexedDB에 동기화한다.

### 부적합 사유

| 문제 | 설명 |
|------|------|
| Provider 교체 필요 | `QueryClientProvider` → `PersistQueryClientProvider`로 교체해야 함 |
| 데이터 구조 종속 | 저장 형태가 React Query dehydrated state로, Copilot이 읽을 때 파싱 필요 |
| 전체 캐시 직렬화 | 불필요한 데이터까지 IndexedDB에 저장됨 |
| 패키지 추가 | `@tanstack/react-query-persist-client` 설치 필요 |
| 프론트엔드 팀 부담 | Provider 교체는 앱 전체에 영향을 줄 수 있어 리뷰 부담이 큼 |

---

## 방식 4: Global Query Event Listener

### 개요

React Query의 QueryCache에 글로벌 이벤트 리스너를 등록하여,
쿼리가 성공할 때마다 IndexedDB에 저장한다.

### 동작 흐름

```
useQuery → Axios → API Server → Response → React Query 캐시
                                                    │
                                          onSuccess (global)
                                                    │
                                                    ▼
                                              IndexedDB
```

### 구현 예시

```javascript
// src/main.jsx (기존 파일 수정)

import { saveToCopilotCache } from './service/copilot/indexeddb-cache';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// 글로벌 캐시 이벤트 구독
queryClient.getQueryCache().subscribe((event) => {
  if (event.type === 'updated' && event.action.type === 'success') {
    const query = event.query;
    const queryKey = query.queryKey;

    // FinOps 관련 쿼리만 필터링
    const cacheTargets = ['cost', 'asset', 'billing', 'budget', 'anomaly'];
    if (cacheTargets.some(target => queryKey.includes(target))) {
      saveToCopilotCache({
        key: JSON.stringify(queryKey),
        data: query.state.data,
        timestamp: Date.now()
      }).catch(() => {});
    }
  }
});
```

### 분석

| 항목 | 평가 |
|------|------|
| 수정 파일 | `main.jsx` 1개 + IndexedDB 유틸 파일 1개 추가 |
| 기존 코드 변경 | queryClient 생성 후 subscribe 추가 (기존 설정 변경 없음) |
| 첫 방문 저장 보장 | **보장됨** - 쿼리 성공 이벤트에 연동 |
| 저장 대상 선별 | queryKey 기반 필터링 |
| 기존 기능 영향 | 없음 (이벤트 구독만, 기존 동작 미변경) |
| 에러 격리 | catch로 무시 가능 |
| 프론트엔드 팀 협조 | **필요** (main.jsx에 코드 추가) |
| **API 커버리지** | **React Query를 거치는 호출만** |

### 장점

- 기존 QueryClient 설정을 변경하지 않고 subscribe만 추가
- React Query의 queryKey로 의미 있는 필터링 가능
- 이미 파싱된 데이터(response.data)가 저장됨 (Copilot이 바로 사용 가능)
- React Query의 중복 제거, 캐시 관리 혜택을 그대로 받음

### 단점

- queryKey 네이밍 규칙을 파악해야 필터링 가능
- **React Query를 거치지 않는 API 호출은 누락** (컴포넌트 내 직접 axios 호출 등)
- React Query 내부 이벤트 구조에 의존 (메이저 버전 업데이트 시 확인 필요)

### ⚠️ OpsNow 환경에서의 한계: 화면 데이터 커버리지

```
React Query 경유 여부 (페이지별):

  Credit, KPIs, Policy, Commitments, CDN  → O (React Query hooks)
  Overview                                → X (Redux dispatch)
  Optimization Settings (12개 탭)          → X (useState + useEffect + 직접 axios)
  Usage Monitor                           → X (useState + useEffect + 직접 axios)
  Resource Alert                          → X (useState + useCallback + 직접 axios)
```

**화면 데이터 기준 ~70%만 커버. Overview, Optimization, Usage, Resource Alert 페이지에서
Copilot이 화면 데이터를 알 수 없음.**

---

## 방식 5: Global Network Override ← 권장

### 개요

브라우저의 `window.fetch`와 `XMLHttpRequest`를 모두 래핑하여,
어떤 Axios 어댑터를 사용하든 모든 네트워크 요청의 응답을 IndexedDB에 저장한다.
기존 코드 수정 없이, 앱 초기화 전에 오버라이드한다.

### 동작 흐름

```
앱 초기화 전: window.fetch + XMLHttpRequest를 래핑

                  21개+ Axios 인스턴스 (패턴 A, B, C 전부)
                          │
                          ▼
                  Axios adapter 선택
                  ├── xhr adapter ──→ XMLHttpRequest (오버라이드됨) ─┐
                  │                                                 ├─→ IndexedDB 저장
                  └── fetch adapter ─→ window.fetch (오버라이드됨) ──┘
                                              │
                                              ▼
                                    원본 요청 수행 → Response → Axios → React Query
```

### Axios 어댑터 상황과 대응

OpsNow 프론트엔드의 Axios 인스턴스들은 `adapter`를 명시적으로 설정하지 않는다.

```
공통 라이브러리 의존성 체인:
  com-cm-foweb
    └── opsnow-finops-common-ui-loader
          ├── axios: "^1.7.2"                ← 실제 설치 버전 결정
          └── opsnow-finops-common-axios
                └── lib/main.js:71-75
                      axios.create({
                        baseURL: '/',
                        headers: resultHeaders,
                        timeout,
                      })
                      // adapter 설정 없음
```

Axios 1.7+에서 adapter 미설정 시 기본값은 `['xhr', 'fetch']` (xhr 우선).
**브라우저에서 XMLHttpRequest가 항상 사용 가능하므로 xhr이 선택될 가능성이 높다.**

따라서 `window.fetch` override만으로는 불충분하며,
**`XMLHttpRequest`도 함께 오버라이드해야 어댑터와 무관하게 전체 커버가 가능하다.**

### 구현 예시

```javascript
// public/copilot-network-hook.js (신규 파일, index.html에서 로드)

(function() {
  const CACHE_TARGETS = ['/cost/', '/asset/', '/billing/'];

  function shouldCache(url) {
    try {
      const pathname = new URL(url, location.origin).pathname;
      return CACHE_TARGETS.some(prefix => pathname.startsWith(prefix));
    } catch { return false; }
  }

  // ─────────────────────────────────────────────
  // 1. fetch override
  // ─────────────────────────────────────────────
  const originalFetch = window.fetch;

  window.fetch = function(...args) {
    const request = new Request(...args);
    const url = request.url;

    return originalFetch.apply(this, args).then(response => {
      if (response.ok && shouldCache(url)) {
        const clone = response.clone();
        clone.json().then(data => {
          saveToCopilotCache({ url, data, timestamp: Date.now() });
        }).catch(() => {});
      }
      return response;
    });
  };

  // ─────────────────────────────────────────────
  // 2. XMLHttpRequest override
  // ─────────────────────────────────────────────
  const originalXHROpen = XMLHttpRequest.prototype.open;
  const originalXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this._copilotUrl = url;
    this._copilotMethod = method;
    return originalXHROpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.send = function(body) {
    if (shouldCache(this._copilotUrl)) {
      this.addEventListener('load', function() {
        if (this.status >= 200 && this.status < 300) {
          try {
            const data = JSON.parse(this.responseText);
            saveToCopilotCache({
              url: this._copilotUrl,
              data,
              timestamp: Date.now()
            });
          } catch {}
        }
      });
    }
    return originalXHRSend.apply(this, [body]);
  };

  // ─────────────────────────────────────────────
  // 3. IndexedDB 저장 함수
  // ─────────────────────────────────────────────
  function saveToCopilotCache({ url, data, timestamp }) {
    // IndexedDB 저장 로직 (PoC에서 구현)
  }
})();
```

```html
<!-- index.html에 한 줄 추가 (앱 스크립트보다 먼저 로드) -->
<script src="/copilot-network-hook.js"></script>
```

### 저장 대상 선별 및 데이터 관리

Network Override는 모든 네트워크 요청이 통과하지만,
**저장은 조건에 맞는 것만** 수행한다. 관심사가 두 단계로 분리된다.

```
네트워크 요청 (전체)
    │
    ▼
[1단계: 인터셉트] fetch/XHR override → 모든 요청을 관찰
    │
    ▼
[2단계: 필터링]   shouldCache()      → 저장 대상만 선별
    │
    ▼
[3단계: 저장/관리] saveToCopilotCache() → IndexedDB 저장 정책 적용
```

#### 필터링 기준 (shouldCache)

| 기준 | 예시 | 용도 |
|------|------|------|
| URL 경로 패턴 | `/cost/`, `/asset/`, `/billing/` | 화면 데이터 API만 선별 |
| HTTP 메서드 | GET만 저장, POST/PUT/DELETE 제외 | 조회 데이터만 캐싱 |
| 응답 상태 | 200~299만 저장 | 에러 응답 제외 |
| Content-Type | `application/json`만 저장 | 파일 다운로드 등 제외 |
| 응답 크기 | 10MB 초과 시 스킵 | 대용량 응답 보호 |

#### 데이터 관리 정책 (saveToCopilotCache)

| 정책 | 설명 |
|------|------|
| **덮어쓰기** | 동일 URL의 이전 데이터를 최신으로 교체 (항상 현재 화면 데이터) |
| **TTL 관리** | timestamp 기반 만료. 일정 시간 경과 시 자동 삭제 |
| **용량 관리** | 저장 건수/용량 상한 설정. 초과 시 오래된 항목부터 제거 |
| **메뉴별 분리** | 현재 페이지 경로(`location.pathname`)를 키에 포함하여 메뉴별 데이터 구분 |
| **중복 방지** | URL + params 조합으로 유일 키 생성. 리트라이 중복 저장 방지 |

이 구조의 핵심은 **"무엇을 잡을 것인가"(Network Override)와 "무엇을 저장/관리할 것인가"(IndexedDB 로직)가
분리**되어 있어, 각각 독립적으로 정책을 조정할 수 있다는 점이다.

### 분석

| 항목 | 평가 |
|------|------|
| 수정 파일 | `index.html` 1줄 추가 + hook 스크립트 1개 추가 |
| 기존 코드 변경 | 없음 (index.html에 script 태그 추가만) |
| 첫 방문 저장 보장 | **보장됨** - 앱 로드 전에 오버라이드됨 |
| 저장 대상 선별 | URL 패턴으로 필터링 |
| 기존 기능 영향 | 원본 response/XHR를 그대로 반환하므로 없음 |
| 에러 격리 | catch/try로 무시 가능 |
| 프론트엔드 팀 협조 | **최소** (index.html에 script 1줄) |
| **API 커버리지** | **전체 (41/41 파일)** - xhr + fetch 모두 커버 |

### 장점

- **앱 코드 수정 없이 index.html에 script 태그 1줄만 추가**
- 앱보다 먼저 로드되므로 **첫 방문 API 응답도 100% 저장**
- **Axios 어댑터(xhr/fetch)와 무관하게 전체 커버**
- Axios 인스턴스가 몇 개든, 어디서 생성되든 상관없이 전부 잡힘
- Copilot 위젯과 함께 독립 배포 가능
- 공통 라이브러리 리트라이로 인한 중복도 URL 기반 dedup으로 일괄 처리 가능

### 단점

- 글로벌 fetch + XHR을 오버라이드하는 것은 안티패턴으로 간주될 수 있음
- 다른 라이브러리가 fetch/XHR을 오버라이드하면 충돌 가능
- 디버깅 시 원본과 구분이 어려움
- fetch만 오버라이드하는 것보다 구현 복잡도가 높아짐

---

## 방식 비교 요약

| 항목 | 1. Axios Interceptor | 2. Service Worker | 3. RQ Persister | 4. RQ Event | **5. Network Override** |
|------|---------------------|-------------------|-----------------|-------------|------------------------|
| **첫 방문 저장** | O | **X** | O | O | **O** |
| **API 커버리지** | **부분 (~1/4)** | 전체 | RQ 경유만 | RQ 경유만 | **전체** |
| **화면 데이터 커버리지** | ~25% | 전체 | ~70% | **~70%** | **100%** |
| **Axios 어댑터 무관** | O (Axios 위) | O (네트워크 레벨) | O (RQ 위) | O (RQ 위) | **O (xhr+fetch 모두)** |
| **기존 코드 수정** | client.js 외 다수 | 0개 | main.jsx 1개 | main.jsx 1개 | **index.html 1줄** |
| **수정 난이도** | 높음 (분산) | 없음 | 중간 | 낮음 | **낮음** |
| **패키지 추가** | 없음 | 없음 | 1개 | 없음 | **없음** |
| **저장 데이터 형태** | Axios response | raw Response | RQ dehydrated | RQ parsed data | **raw JSON** |
| **Copilot 읽기 용이성** | 좋음 | 보통 | 파싱 필요 | 좋음 | **좋음** |
| **에러 격리** | 완전 | 완전 | 높음 | 완전 | **완전** |
| **프론트엔드 팀 협조** | 높음 | 불필요 | 필요 | 필요 | **최소** |
| **부작용 위험** | 없음 | 없음 | 낮음 | 없음 | 충돌 가능 |

---

## OpsNow 환경 적합성 평가

### 방식 2 (Service Worker) → 탈락

첫 방문 시 API 응답 저장이 보장되지 않아 Copilot 핵심 요구사항 미충족.

### 방식 3 (RQ Persister) → 부적합

Provider 교체 부담이 크고, 저장 데이터가 React Query 내부 구조에 종속됨.

### 방식 1 (Axios Interceptor) → 단독 사용 부적합

OpsNow의 Axios 인스턴스가 21개+ 분산(3가지 패턴)되어 있어,
`client.js` 팩토리에만 interceptor를 걸면 전체 API의 약 1/4만 커버.
전체 커버를 위해서는 `getAxios()` 공통 라이브러리(외부 패키지), 직접 생성 인스턴스 11개+,
컴포넌트 인스턴스 12개+에 각각 interceptor를 추가해야 하므로 현실적이지 않음.

`getAxios()`로 인스턴스를 통일하는 방안도 검토했으나, **싱글턴 패턴 + baseURL 고정(`/`) +
timeout 1개 제한**으로 인해 다양한 baseURL/timeout이 필요한 현재 구조를 수용할 수 없다.
통일을 위해서는 전사 공통 라이브러리 설계 변경이 필요하며, 목적 대비 비용이 과도하다.

### 방식 4 (RQ Event) → 가능하나 불완전

React Query를 거치는 호출만 잡히므로 컴포넌트 내 직접 axios 호출은 누락.

**"화면 데이터만 저장하면 된다"는 관점에서 재평가:**

OpsNow 화면 데이터의 ~70%가 React Query를 경유하므로 방식 4의 실질적 커버리지가 올라간다.
그러나 나머지 ~30%가 누락되며, 해당 페이지들이 핵심 메뉴를 포함한다.

```
방식 4로 커버되는 페이지:
  O  Credit, FinOps KPIs, Policy Management, My Commitments, CDN Dashboard

방식 4로 커버되지 않는 페이지:
  X  Overview (Dashboard)          ← Redux dispatch
  X  Optimization Settings (12탭)  ← useState + useEffect + 직접 axios
  X  Usage Monitor                 ← useState + useEffect + 직접 axios
  X  Resource Alert                ← useState + useCallback + 직접 axios
```

**누락 페이지의 의미:**
- Overview와 Optimization은 OpsNow 핵심 메뉴
- 해당 페이지에서 "이 화면에 보이는 수치가 뭐야?" 류의 질문에 응답 불가
- FAQ/Manual RAG나 Smart Fallback으로 대응은 가능하나, 화면 맥락 기반 응답은 불가

**React Query 마이그레이션 추세:**
현재 최신 페이지들(KPIs, Commitments 등)은 모두 React Query custom hooks를 사용.
Optimization, Overview 등 레거시 페이지가 마이그레이션되면 커버리지가 자연 증가하지만,
마이그레이션 시점을 Copilot이 통제할 수 없다.

### 방식 5 (Network Override) → 권장

| 결정 요인 | 평가 |
|----------|------|
| 커버리지 | **전체** - xhr + fetch 모두 오버라이드하여 어댑터 무관 |
| 화면 데이터 커버리지 | **100%** - fetching 패턴(RQ/Redux/직접 axios)과 무관 |
| 첫 방문 저장 | **보장** - 앱 로드 전 오버라이드 |
| 코드 수정 범위 | **최소** - index.html에 script 1줄 |
| 프론트엔드 팀 부담 | **최소** - 앱 코드 변경 없음 |
| 에러 격리 | **완전** - 저장 실패해도 원본 동작에 영향 없음 |

OpsNow 프론트엔드의 특성을 감안할 때:
- Axios 인스턴스가 3가지 패턴으로 분산 (41개 파일)
- 공통 라이브러리의 Axios adapter가 xhr 우선 (adapter 미설정, Axios ^1.7.2)
- `getAxios()` 싱글턴 구조로 인스턴스 통일 불가
- 화면 데이터 fetching이 React Query(~70%), Redux(~15%), 직접 axios(~15%)로 분산
- 단기간 내 구조 정리가 어려운 현실

**`window.fetch` + `XMLHttpRequest`를 모두 오버라이드하는 방식 5가
유일하게 어댑터, 인스턴스 구조, fetching 패턴에 무관하게 전체 화면 데이터 커버리지를 보장한다.**

---

## 방식 선택 옵션

### 옵션 A: 방식 5 단독 (100% 커버, 즉시 적용)

```
index.html에 script 1줄 추가
  → fetch + XHR 오버라이드
  → 모든 API 응답을 URL 패턴으로 필터링
  → IndexedDB에 저장
```

- 장점: 100% 커버, 코드 변경 최소, fetching 패턴 무관
- 단점: URL 패턴 기반 필터링만 가능 (의미론적 메타데이터 없음)

### 옵션 B: 방식 4 단독 (70% 커버, 점진적 확대)

```
main.jsx에 QueryCache subscribe 추가
  → React Query 성공 이벤트 구독
  → queryKey 기반 필터링
  → IndexedDB에 저장
```

- 장점: queryKey로 의미론적 필터링, React Query 마이그레이션에 따라 자연 확대
- 단점: Overview, Optimization 등 핵심 메뉴 누락 (현시점)

### 옵션 C: 방식 5 + 방식 4 하이브리드 (100% 커버 + 의미론적 메타데이터)

```
React Query 경유 데이터  → 방식 4 (queryKey 메타데이터 포함 저장)
React Query 미경유 데이터 → 방식 5 (URL 기반 저장)
```

- 장점: 100% 커버 + React Query 데이터에 대해 queryKey 기반 풍부한 메타데이터
- 단점: 두 방식 동시 운영 → 중복 저장 가능 (dedup 로직 필요), 구현 복잡도 증가

---

### PoC 검증 필요 사항

방식 5 채택 시, 다음 항목을 PoC에서 검증해야 한다:

| 검증 항목 | 내용 |
|----------|------|
| Axios adapter 런타임 확인 | 실제로 xhr/fetch 중 어느 것이 사용되는지 브라우저에서 확인 |
| XHR override 안정성 | XMLHttpRequest.prototype 오버라이드가 Axios 동작에 부작용을 일으키지 않는지 |
| Response clone/parse 성능 | 대량 API 응답 처리 시 메모리/성능 영향 |
| 중복 저장 방지 | 공통 라이브러리 리트라이(GET 최대 3회)로 인한 중복 처리 |
| IndexedDB 저장 키 설계 | URL + params 조합의 유일 키 생성 방식 |
| fetch/XHR 충돌 확인 | Sentry 등 다른 라이브러리가 fetch/XHR을 오버라이드하는 경우 동작 확인 |
| xhr + fetch 동시 오버라이드 시 중복 | 하나의 Axios 요청이 xhr과 fetch 모두를 트리거하지 않는지 확인 |
