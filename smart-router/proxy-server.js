/**
 * OpenClaw Smart Router Proxy Server
 * Runs on port 8081 as an OpenAI-compatible endpoint.
 * OpenClaw points to http://localhost:8081/v1/chat/completions as its "model".
 * This proxy intercepts every request, scores complexity, routes to correct model.
 *
 * Architecture (agreed by Claude + ChatGPT + Gemini):
 *   OpenClaw → localhost:8081 → Gemma 2B / Kimi K2.5 / Claude Sonnet
 *
 * Routing rules:
 *   Trading keywords        → Kimi K2.5  (TRADING_GUARDRAIL - never to Gemma)
 *   Complexity score 0-30   → Gemma 2B   (local, free)
 *   Complexity score 31-70  → Kimi K2.5  (free API)
 *   Complexity score 71-100 → Claude Sonnet (paid, use sparingly)
 *   Any error/crash         → Kimi K2.5  (failsafe)
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

// ── Config ────────────────────────────────────────────────────────────────────
const PORT = 8081;
const LOG_FILE = path.join(__dirname, '../logs/proxy-routing.log');
const CONFIG_FILE = '/home/ubuntu/.openclaw/openclaw.json';

// Load API keys from openclaw.json
let config = {};
try {
  config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
} catch (e) {
  console.error('[PROXY] Failed to load openclaw.json:', e.message);
  process.exit(1);
}

const NVIDIA_API_KEY = config.env?.vars?.NVIDIA_NIM_API_KEY || '';
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || '';

// ── Trading keywords (mirrors model-capabilities.js) ─────────────────────────
const TRADING_KEYWORDS = [
  'paper yes', 'paper no', 'paper_yes', 'paper_no',
  'buy', 'sell', 'trade', 'position', 'signal', 'market',
  'polymarket', 'whale', 'proposal', 'bet', 'stake',
  'probability', 'odds', 'resolution', 'outcome',
  'usdc', 'matic', 'polygon', 'wallet', 'portfolio',
  'entry', 'exit', 'stop loss', 'take profit',
  'bull', 'bear', 'long', 'short', 'leverage'
];

// ── Complexity scorer ─────────────────────────────────────────────────────────
function scoreComplexity(text) {
  if (!text || typeof text !== 'string') return 0;
  const t = text.toLowerCase().replace(/_/g, ' ');

  // Trading guardrail check
  for (const kw of TRADING_KEYWORDS) {
    if (t.includes(kw)) return -1; // -1 = force Kimi via guardrail
  }

  let score = 0;
  const words = t.split(/\s+/).length;

  // Length scoring
  if (words > 50) score += 30;
  else if (words > 20) score += 15;
  else if (words > 10) score += 5;

  // Complexity indicators
  const complexWords = ['analyze', 'explain', 'compare', 'evaluate', 'strategy',
    'financial', 'model', 'forecast', 'risk', 'correlation',
    'reasoning', 'complex', 'detailed', 'comprehensive'];
  for (const w of complexWords) {
    if (t.includes(w)) score += 10;
  }

  // Questions
  if (t.includes('?')) score += 5;
  if ((t.match(/\?/g) || []).length > 2) score += 10;

  return Math.min(score, 100);
}

// ── Route decision ────────────────────────────────────────────────────────────
function routeRequest(messages) {
  // Extract last user message
  const lastUser = [...messages].reverse().find(m => m.role === 'user');
  const text = lastUser?.content || '';

  const score = scoreComplexity(text);

  if (score === -1) {
    return { model: 'kimi', reason: 'TRADING_GUARDRAIL', score: 0 };
  }
  if (score <= 30) {
    return { model: 'gemma', reason: `Low complexity (${score}) → Gemma`, score };
  }
  if (score <= 70) {
    return { model: 'kimi', reason: `Medium complexity (${score}) → Kimi`, score };
  }
  return { model: 'sonnet', reason: `High complexity (${score}) → Sonnet`, score };
}

// ── Log routing decision ──────────────────────────────────────────────────────
function logDecision(route, msgSnippet, latencyMs) {
  const entry = JSON.stringify({
    ts: new Date().toISOString(),
    msg_snippet: msgSnippet?.slice(0, 40) || '',
    model: route.model,
    score: route.score,
    reason: route.reason,
    latency_ms: latencyMs
  });
  try {
    fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
    fs.appendFileSync(LOG_FILE, entry + '\n');
  } catch (e) {
    // non-fatal
  }
  console.log('[PROXY]', entry);
}

// ── Call Gemma (local Ollama) ─────────────────────────────────────────────────
function callGemma(messages) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: 'gemma2:2b',
      messages,
      stream: false
    });
    const req = http.request({
      hostname: '127.0.0.1',
      port: 11434,
      path: '/v1/chat/completions',
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('Gemma parse error: ' + e.message)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('Gemma timeout')); });
    req.write(body);
    req.end();
  });
}

// ── Call Kimi via NVIDIA NIM ──────────────────────────────────────────────────
function callKimi(messages) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: 'moonshotai/kimi-k2.5',
      messages,
      stream: false,
      max_tokens: 6000
    });
    const req = https.request({
      hostname: 'integrate.api.nvidia.com',
      path: '/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${NVIDIA_API_KEY}`,
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('Kimi parse error: ' + e.message)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(60000, () => { req.destroy(); reject(new Error('Kimi timeout')); });
    req.write(body);
    req.end();
  });
}

// ── Call Claude Sonnet ────────────────────────────────────────────────────────
function callSonnet(messages) {
  return new Promise((resolve, reject) => {
    // Convert to Anthropic format
    const system = messages.find(m => m.role === 'system')?.content || '';
    const userMessages = messages.filter(m => m.role !== 'system');

    const body = JSON.stringify({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      system: system || undefined,
      messages: userMessages
    });
    const req = https.request({
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          // Convert Anthropic response → OpenAI format
          const openaiFormat = {
            id: parsed.id || 'proxy-sonnet',
            object: 'chat.completion',
            model: 'claude-sonnet-4-20250514',
            choices: [{
              index: 0,
              message: {
                role: 'assistant',
                content: parsed.content?.[0]?.text || ''
              },
              finish_reason: parsed.stop_reason || 'stop'
            }],
            usage: parsed.usage
          };
          resolve(openaiFormat);
        } catch (e) { reject(new Error('Sonnet parse error: ' + e.message)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(60000, () => { req.destroy(); reject(new Error('Sonnet timeout')); });
    req.write(body);
    req.end();
  });
}

// ── Main proxy handler ────────────────────────────────────────────────────────
async function handleRequest(body) {
  const messages = body.messages || [];
  const lastUser = [...messages].reverse().find(m => m.role === 'user');
  const snippet = lastUser?.content?.slice(0, 40) || '';

  const start = Date.now();
  const route = routeRequest(messages);

  try {
    let response;

    if (route.model === 'gemma') {
      try {
        response = await callGemma(messages);
      } catch (gemmaErr) {
        console.error('[PROXY] Gemma failed, falling back to Kimi:', gemmaErr.message);
        route.model = 'kimi';
        route.reason += ' (Gemma failed → Kimi fallback)';
        response = await callKimi(messages);
      }
    } else if (route.model === 'sonnet') {
      try {
        response = await callSonnet(messages);
      } catch (sonnetErr) {
        console.error('[PROXY] Sonnet failed, falling back to Kimi:', sonnetErr.message);
        route.model = 'kimi';
        route.reason += ' (Sonnet failed → Kimi fallback)';
        response = await callKimi(messages);
      }
    } else {
      response = await callKimi(messages);
    }

    logDecision(route, snippet, Date.now() - start);
    return { success: true, response };

  } catch (err) {
    // Ultimate failsafe — always return something
    console.error('[PROXY] All models failed, emergency fallback:', err.message);
    logDecision({ model: 'error-fallback', reason: err.message, score: -99 }, snippet, Date.now() - start);
    return {
      success: false,
      response: {
        id: 'proxy-error',
        object: 'chat.completion',
        model: 'kimi-fallback',
        choices: [{
          index: 0,
          message: { role: 'assistant', content: 'Proxy routing error — please retry.' },
          finish_reason: 'stop'
        }]
      }
    };
  }
}

// ── HTTP Server ───────────────────────────────────────────────────────────────
const server = http.createServer((req, res) => {
  // Health check
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', port: PORT, service: 'smart-router-proxy' }));
    return;
  }

  // OpenAI-compatible chat completions endpoint
  if (req.method === 'POST' && req.url === '/v1/chat/completions') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const parsed = JSON.parse(body);
        const { success, response } = await handleRequest(parsed);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(response));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[PROXY] Smart Router Proxy running on http://127.0.0.1:${PORT}`);
  console.log(`[PROXY] Health check: http://127.0.0.1:${PORT}/health`);
  console.log(`[PROXY] Endpoint: http://127.0.0.1:${PORT}/v1/chat/completions`);
  console.log(`[PROXY] Routing: Gemma(0-30) → Kimi(31-70) → Sonnet(71-100)`);
  console.log(`[PROXY] Trading guardrail: all trading keywords → Kimi`);
});

server.on('error', (err) => {
  console.error('[PROXY] Server error:', err.message);
  process.exit(1);
});

module.exports = server;
