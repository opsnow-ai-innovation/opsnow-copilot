/**
 * Mock API Server — Phase 1 테스트용
 *
 * 실행: node mock-api-server.js
 * 포트: 3456
 *
 * 엔드포인트:
 *   GET  /api/cost/summary      → 비용 요약 데이터
 *   POST /api/cost/detail       → 비용 상세 데이터
 *   GET  /api/asset/list        → 자산 목록 데이터
 *   POST /api/asset/detail      → 자산 상세 데이터
 *   GET  /auth/token            → 인증 토큰 (캐시 비대상)
 *   GET  /api/billing/overview  → 빌링 개요 데이터
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3456;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
};

// Mock 응답 데이터
const RESPONSES = {
  '/api/cost/summary': {
    totalCost: 125340.50,
    currency: 'USD',
    period: '2025-01',
    breakdown: [
      { service: 'EC2', cost: 45000 },
      { service: 'RDS', cost: 32000 },
      { service: 'S3', cost: 8500 },
      { service: 'Lambda', cost: 3200 },
    ],
  },
  '/api/cost/detail': {
    items: [
      { id: 1, account: 'prod-aws', service: 'EC2', cost: 45000, region: 'ap-northeast-2' },
      { id: 2, account: 'prod-aws', service: 'RDS', cost: 32000, region: 'ap-northeast-2' },
      { id: 3, account: 'dev-aws', service: 'S3', cost: 8500, region: 'us-east-1' },
    ],
    total: 85500,
    page: 1,
    pageSize: 20,
  },
  '/api/asset/list': {
    assets: [
      { id: 'i-abc123', type: 'EC2', name: 'web-server-01', status: 'running' },
      { id: 'i-def456', type: 'EC2', name: 'web-server-02', status: 'running' },
      { id: 'db-xyz789', type: 'RDS', name: 'main-db', status: 'available' },
    ],
    totalCount: 3,
  },
  '/api/asset/detail': {
    id: 'i-abc123',
    type: 'EC2',
    name: 'web-server-01',
    instanceType: 'm5.xlarge',
    status: 'running',
    region: 'ap-northeast-2',
    monthlyCost: 234.56,
    tags: { env: 'production', team: 'platform' },
  },
  '/auth/token': {
    accessToken: 'mock-jwt-token-xxxxx',
    expiresIn: 3600,
    tokenType: 'Bearer',
  },
  '/api/billing/overview': {
    currentMonth: 125340.50,
    previousMonth: 118200.00,
    changePercent: 6.04,
    forecast: 132000.00,
  },
};

const server = http.createServer((req, res) => {
  // CORS 헤더
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  // Preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = req.url.split('?')[0]; // query string 제거

  // ─── 정적 파일 서빙 (test.html, *.js) ───
  if (url === '/' || url === '/test.html' || url.endsWith('.js') || url.endsWith('.css')) {
    const fileName = url === '/' ? '/test.html' : url;
    const filePath = path.join(__dirname, fileName);
    const ext = path.extname(filePath);

    try {
      const content = fs.readFileSync(filePath);
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain' });
      res.end(content);
      console.log(`[STATIC] ${fileName}`);
      return;
    } catch {
      // 파일 없으면 API 라우팅으로 진행
    }
  }

  const data = RESPONSES[url];

  if (data) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    console.log(`[${req.method}] ${req.url} → 200`);
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not Found', path: req.url }));
    console.log(`[${req.method}] ${req.url} → 404`);
  }
});

server.listen(PORT, () => {
  console.log(`\nMock API Server running at http://localhost:${PORT}`);
  console.log(`\n테스트 페이지: http://localhost:${PORT}/test.html`);
  console.log('\nEndpoints:');
  Object.keys(RESPONSES).forEach((path) => {
    console.log(`  http://localhost:${PORT}${path}`);
  });
  console.log('');
});
