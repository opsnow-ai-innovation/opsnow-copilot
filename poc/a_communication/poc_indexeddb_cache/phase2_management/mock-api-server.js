/**
 * Mock API Server — Phase 2 테스트용
 *
 * 실행: node mock-api-server.js
 * 포트: 3456
 *
 * Phase 1 엔드포인트 + 추가 시나리오:
 *   - DELETE 메서드 (필터링 대상)
 *   - 500 에러 응답
 *   - text/html 응답 (비 JSON)
 *   - 대용량 JSON 응답 (10MB+)
 *   - 동일 URL 다른 데이터 (덮어쓰기 테스트)
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3456;

// 정적 파일 MIME 타입
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
};

// 호출 카운터 (덮어쓰기 테스트용)
let callCount = 0;

// Mock 응답 데이터
const RESPONSES = {
  '/api/cost/summary': () => ({
    totalCost: 125340.5 + callCount++,
    currency: 'USD',
    period: '2025-01',
    callNumber: callCount,
    breakdown: [
      { service: 'EC2', cost: 45000 },
      { service: 'RDS', cost: 32000 },
      { service: 'S3', cost: 8500 },
    ],
  }),
  '/api/cost/detail': () => ({
    items: [
      { id: 1, account: 'prod-aws', service: 'EC2', cost: 45000 },
      { id: 2, account: 'prod-aws', service: 'RDS', cost: 32000 },
    ],
    total: 77000,
    callNumber: callCount++,
  }),
  '/api/asset/list': () => ({
    assets: [
      { id: 'i-abc123', type: 'EC2', name: 'web-server-01', status: 'running' },
      { id: 'i-def456', type: 'EC2', name: 'web-server-02', status: 'stopped' },
    ],
    totalCount: 2,
  }),
  '/api/asset/detail': () => ({
    id: 'i-abc123',
    type: 'EC2',
    name: 'web-server-01',
    instanceType: 'm5.xlarge',
    status: 'running',
    monthlyCost: 234.56,
  }),
  '/auth/token': () => ({
    accessToken: 'mock-jwt-token',
    expiresIn: 3600,
    tokenType: 'Bearer',
  }),
  '/api/billing/overview': () => ({
    currentMonth: 125340.5,
    previousMonth: 118200.0,
    changePercent: 6.04,
    forecast: 132000.0,
  }),
};

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = req.url.split('?')[0];

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

  // ─── 특수 엔드포인트 ───

  // DELETE 메서드 테스트
  if (req.method === 'DELETE' && url === '/api/cost/item/123') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ deleted: true, id: 123 }));
    console.log(`[DELETE] ${req.url} → 200`);
    return;
  }

  // 500 에러 응답
  if (url === '/api/error/500') {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Internal Server Error' }));
    console.log(`[${req.method}] ${req.url} → 500`);
    return;
  }

  // text/html 응답 (비 JSON)
  if (url === '/api/html-response') {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end('<html><body><h1>HTML Response</h1></body></html>');
    console.log(`[${req.method}] ${req.url} → 200 (text/html)`);
    return;
  }

  // 대용량 응답 (~6MB)
  if (url === '/api/large-response') {
    const items = [];
    for (let i = 0; i < 50000; i++) {
      items.push({
        id: i,
        name: `item-${i}-${'x'.repeat(100)}`,
        value: Math.random() * 1000,
      });
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ items, count: items.length }));
    console.log(`[${req.method}] ${req.url} → 200 (large ~6MB)`);
    return;
  }

  // ─── 일반 엔드포인트 ───

  const handler = RESPONSES[url];
  if (handler) {
    const data = handler();
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
  console.log(`\nMock API Server (Phase 2) running at http://localhost:${PORT}`);
  console.log(`\n테스트 페이지: http://localhost:${PORT}/test.html`);
  console.log('\nEndpoints:');
  Object.keys(RESPONSES).forEach((path) => {
    console.log(`  http://localhost:${PORT}${path}`);
  });
  console.log('\nPhase 2 특수 엔드포인트:');
  console.log(`  DELETE http://localhost:${PORT}/api/cost/item/123  (메서드 필터링)`);
  console.log(`  GET    http://localhost:${PORT}/api/error/500      (에러 응답)`);
  console.log(`  GET    http://localhost:${PORT}/api/html-response  (비 JSON)`);
  console.log(`  GET    http://localhost:${PORT}/api/large-response (대용량 ~6MB)`);
  console.log('');
});
