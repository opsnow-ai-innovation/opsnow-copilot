/**
 * Mock API Server — Phase 3 테스트용
 *
 * 실행: node mock-api-server.js
 * 포트: 3456
 *
 * Phase 2 엔드포인트 + 성능 테스트용:
 *   - GET /api/size/1kb       (1KB JSON)
 *   - GET /api/size/100kb     (100KB JSON)
 *   - GET /api/size/5mb       (5MB JSON)
 *   - GET /api/malformed-json (깨진 JSON — 파싱 실패 테스트)
 *   - GET /api/slow/2000      (2초 지연 응답)
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

// ─── 사이즈별 응답 생성 ───

function generatePayload(targetBytes) {
  const items = [];
  const itemSize = 120; // 대략 한 항목 크기
  const count = Math.ceil(targetBytes / itemSize);
  for (let i = 0; i < count; i++) {
    items.push({ id: i, name: `item-${i}`, value: Math.random() * 1000 });
  }
  return { items, count: items.length, generatedSize: `~${Math.round(targetBytes / 1024)}KB` };
}

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

  // ─── Phase 3 성능 테스트 엔드포인트 ───

  // 1KB 응답
  if (url === '/api/size/1kb') {
    const data = generatePayload(1024);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    console.log(`[${req.method}] ${url} → 200 (1KB)`);
    return;
  }

  // 100KB 응답
  if (url === '/api/size/100kb') {
    const data = generatePayload(100 * 1024);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    console.log(`[${req.method}] ${url} → 200 (100KB)`);
    return;
  }

  // 5MB 응답
  if (url === '/api/size/5mb') {
    const data = generatePayload(5 * 1024 * 1024);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
    console.log(`[${req.method}] ${url} → 200 (5MB)`);
    return;
  }

  // 깨진 JSON (Content-Type은 json이지만 body가 유효하지 않음)
  if (url === '/api/malformed-json') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end('{ invalid json :::');
    console.log(`[${req.method}] ${url} → 200 (malformed JSON)`);
    return;
  }

  // 지연 응답 (ms 파라미터)
  const slowMatch = url.match(/^\/api\/slow\/(\d+)$/);
  if (slowMatch) {
    const delayMs = parseInt(slowMatch[1], 10);
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ delayed: true, delayMs }));
      console.log(`[${req.method}] ${url} → 200 (${delayMs}ms delayed)`);
    }, delayMs);
    return;
  }

  // ─── Phase 2 특수 엔드포인트 ───

  if (req.method === 'DELETE' && url === '/api/cost/item/123') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ deleted: true, id: 123 }));
    console.log(`[DELETE] ${url} → 200`);
    return;
  }

  if (url === '/api/error/500') {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Internal Server Error' }));
    console.log(`[${req.method}] ${url} → 500`);
    return;
  }

  if (url === '/api/html-response') {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end('<html><body><h1>HTML Response</h1></body></html>');
    console.log(`[${req.method}] ${url} → 200 (text/html)`);
    return;
  }

  // ─── 일반 엔드포인트 ───

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
  console.log(`\nMock API Server (Phase 3) running at http://localhost:${PORT}`);
  console.log(`\n테스트 페이지: http://localhost:${PORT}/test.html`);
  console.log('\nPhase 3 성능 테스트 엔드포인트:');
  console.log(`  GET http://localhost:${PORT}/api/size/1kb`);
  console.log(`  GET http://localhost:${PORT}/api/size/100kb`);
  console.log(`  GET http://localhost:${PORT}/api/size/5mb`);
  console.log(`  GET http://localhost:${PORT}/api/malformed-json`);
  console.log(`  GET http://localhost:${PORT}/api/slow/{ms}`);
  console.log('');
});
