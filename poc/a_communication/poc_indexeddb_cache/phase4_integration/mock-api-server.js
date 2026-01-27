/**
 * Mock API Server — Phase 4 통합 테스트용
 *
 * 실행: node mock-api-server.js
 * 포트: 3456
 *
 * IndexedDB에 저장할 API 데이터를 제공하는 HTTP 서버.
 * Phase 4에서는 별도 WebSocket 서버(ws-server.py)와 함께 사용합니다.
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

let callCount = 0;

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
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = req.url.split('?')[0];

  // ─── 정적 파일 서빙 ───
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

  // ─── API 엔드포인트 ───
  const handler = RESPONSES[url];
  if (handler) {
    const data = handler();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    console.log(`[${req.method}] ${url} → 200`);
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not Found', path: url }));
    console.log(`[${req.method}] ${url} → 404`);
  }
});

server.listen(PORT, () => {
  console.log(`\nMock API Server (Phase 4) running at http://localhost:${PORT}`);
  console.log(`테스트 페이지: http://localhost:${PORT}/test.html`);
  console.log(`\n별도 WebSocket 서버도 실행하세요:`);
  console.log(`  python ws-server.py  (포트 8765)`);
  console.log('');
});
