#!/usr/bin/env node
/**
 * dry_run_test.js -- Day 1 Smart Router dry-run
 * Tests 30 sample messages. Verifies ZERO trading tasks reach Gemma.
 * Run: node smart-router/dry_run_test.js
 */

const RouterEngine = require('./router-engine');
const router = new RouterEngine({ enableLogging: false });

const GEMMA = 'ollama/gemma2:2b';
const KIMI  = 'nvidia-nim/moonshotai/kimi-k2.5';

// 30 test messages: 10 safe (Gemma OK), 10 trading (must NOT hit Gemma), 10 complex
const tests = [
    // --- SAFE: Gemma allowed ---
    { msg: "hi",                          expectGemma: true,  label: "greeting" },
    { msg: "hello alpha",                 expectGemma: true,  label: "greeting2" },
    { msg: "how are you",                 expectGemma: true,  label: "casual" },
    { msg: "/status",                     expectGemma: true,  label: "status_cmd" },
    { msg: "/help",                       expectGemma: true,  label: "help_cmd" },
    { msg: "good morning",                expectGemma: true,  label: "morning" },
    { msg: "what is the weather",         expectGemma: true,  label: "weather_info" },
    { msg: "tell me a joke",              expectGemma: true,  label: "joke" },
    { msg: "what time is it",             expectGemma: true,  label: "time" },
    { msg: "thanks",                      expectGemma: true,  label: "thanks" },

    // --- TRADING: MUST bypass Gemma (minimum Kimi) ---
    { msg: "whale bought YES on Oscar Best Picture", expectGemma: false, label: "TRADING_whale_oscar" },
    { msg: "show me the signal for this market",     expectGemma: false, label: "TRADING_signal" },
    { msg: "what is my current balance",             expectGemma: false, label: "TRADING_balance" },
    { msg: "PAPER YES",                              expectGemma: false, label: "TRADING_paper_yes" },
    { msg: "PAPER NO",                               expectGemma: false, label: "TRADING_paper_no" },
    { msg: "approve the trade proposal",             expectGemma: false, label: "TRADING_approve" },
    { msg: "what is my pnl today",                   expectGemma: false, label: "TRADING_pnl" },
    { msg: "polymarket whale activity detected",     expectGemma: false, label: "TRADING_polymarket" },
    { msg: "check ledger for open positions",        expectGemma: false, label: "TRADING_ledger" },
    { msg: "did the cron run successfully",          expectGemma: false, label: "TRADING_cron" },
    { msg: "bitcoin price prediction",               expectGemma: false, label: "TRADING_bitcoin" },
    { msg: "eth crypto market update",               expectGemma: false, label: "TRADING_eth" },
    { msg: "oscar resolution date",                  expectGemma: false, label: "TRADING_oscar" },
    { msg: "fed rate decision impact",               expectGemma: false, label: "TRADING_fed" },
    { msg: "scan for new markets",                   expectGemma: false, label: "TRADING_scan" },

    // --- COMPLEX: Should go to Kimi or Claude ---
    { msg: "analyze the whale pattern across 10 markets and suggest kelly sizing", expectGemma: false, label: "COMPLEX_analysis" },
    { msg: "write a detailed report on my portfolio exposure",                     expectGemma: false, label: "COMPLEX_report" },
    { msg: "explain step by step how the divergence calculation works",            expectGemma: false, label: "COMPLEX_explain" },
    { msg: "compare all open positions and recommend which to close first",        expectGemma: false, label: "COMPLEX_compare" },
    { msg: "debug why the bridge is not executing the paper trade",                expectGemma: false, label: "COMPLEX_debug" },
];

// Run all tests
let passed = 0;
let failed = 0;
const failures = [];

console.log("=".repeat(65));
console.log("Smart Router Dry-Run Test -- 30 Messages");
console.log("=".repeat(65));

for (const test of tests) {
    const result = router.route(test.msg);
    const isGemma = result.model === GEMMA;
    const ok = (isGemma === test.expectGemma);

    const icon = ok ? "PASS" : "FAIL";
    const gemmaStr = isGemma ? "Gemma" : (result.model.includes("kimi") ? "Kimi" : "Claude");
    const expected = test.expectGemma ? "Gemma" : "Kimi+";

    console.log(`[${icon}] ${test.label.padEnd(28)} | got=${gemmaStr.padEnd(6)} | expected=${expected.padEnd(6)} | score=${result.score}`);

    if (ok) {
        passed++;
    } else {
        failed++;
        failures.push({ label: test.label, msg: test.msg, got: result.model, tier: result.tier, score: result.score });
    }
}

console.log("=".repeat(65));
console.log(`Results: ${passed} PASSED, ${failed} FAILED out of ${tests.length}`);

// Critical check: zero trading tasks to Gemma
const tradingToGemma = failures.filter(f => f.label.startsWith("TRADING_"));
if (tradingToGemma.length > 0) {
    console.log("\n CRITICAL FAILURE -- Trading tasks reached Gemma:");
    tradingToGemma.forEach(f => console.log(`  - ${f.label}: ${f.msg}`));
    console.log("\n DO NOT ACTIVATE Smart Router until this is fixed.\n");
    process.exit(1);
} else {
    console.log("\n Zero trading tasks reached Gemma -- guardrail working.");
}

if (failed > 0) {
    console.log("\nNon-critical failures (review but not blocking):");
    failures.forEach(f => console.log(`  - ${f.label}: expected ${f.label.startsWith("TRADING") ? "Kimi+" : "Gemma"}, got ${f.got} (score=${f.score})`));
}

if (failed === 0) {
    console.log(" All 30 tests passed. Day 1 complete. Ready for Day 2 shadow mode.\n");
} else {
    console.log("\nDay 1 status: Guardrail OK. Review non-critical failures above.\n");
}
