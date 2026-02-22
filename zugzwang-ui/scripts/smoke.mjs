const API_BASE = (process.env.ZUGZWANG_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = Number(process.env.ZUGZWANG_SMOKE_TIMEOUT_MS || 5000);
const FORCED_RUN_ID = process.env.ZUGZWANG_SMOKE_RUN_ID || "";

async function main() {
  console.log(`[smoke] API base: ${API_BASE}`);

  const envChecks = await apiGet("/api/env-check");
  assert(Array.isArray(envChecks), "Expected /api/env-check to return an array");
  console.log(`[smoke] env-check ok (${envChecks.length} entries)`);

  const runs = await apiGet("/api/runs");
  assert(Array.isArray(runs), "Expected /api/runs to return an array");
  console.log(`[smoke] runs ok (${runs.length} runs indexed)`);

  const jobs = await apiGet("/api/jobs");
  assert(Array.isArray(jobs), "Expected /api/jobs to return an array");
  console.log(`[smoke] jobs ok (${jobs.length} jobs)`);

  const configs = await apiGet("/api/configs");
  assert(configs && typeof configs === "object", "Expected /api/configs to return an object");
  const baselines = Array.isArray(configs.baselines) ? configs.baselines : [];
  const ablations = Array.isArray(configs.ablations) ? configs.ablations : [];
  console.log(`[smoke] configs ok (${baselines.length} baselines / ${ablations.length} ablations)`);

  const firstTemplate = [...baselines, ...ablations][0];
  if (firstTemplate && typeof firstTemplate.path === "string" && firstTemplate.path.length > 0) {
    const payload = {
      config_path: firstTemplate.path,
      overrides: [],
      model_profile: null,
    };
    const validation = await apiPost("/api/configs/validate", payload);
    assert(validation && typeof validation.ok === "boolean", "Expected validate response shape");
    console.log(`[smoke] config validate ok (${validation.ok ? "ok" : "invalid"})`);

    const preview = await apiPost("/api/configs/preview", payload);
    assert(preview && typeof preview.run_id === "string", "Expected preview response with run_id");
    console.log(`[smoke] config preview ok (${preview.run_id})`);
  } else {
    console.log("[smoke] no config templates found, skipping validate/preview checks");
  }

  if (runs.length === 0) {
    console.log("[smoke] no runs found, skipping run-detail/replay checks");
    return;
  }

  const runId = FORCED_RUN_ID || String(runs[0].run_id || "");
  assert(runId.length > 0, "Invalid run id");

  const summary = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
  assert(summary && typeof summary === "object", "Expected run summary object");
  console.log(`[smoke] run summary ok (${runId})`);

  const games = await apiGet(`/api/runs/${encodeURIComponent(runId)}/games`);
  assert(Array.isArray(games), "Expected games list to be an array");
  console.log(`[smoke] games ok (${games.length} records)`);

  if (games.length === 0) {
    console.log("[smoke] run has no games, skipping replay frame checks");
    return;
  }

  const gameNumber = Number(games[0].game_number);
  assert(Number.isFinite(gameNumber), "Invalid game number");

  const game = await apiGet(`/api/runs/${encodeURIComponent(runId)}/games/${gameNumber}`);
  assert(game && typeof game === "object", "Expected game payload object");
  console.log(`[smoke] game detail ok (#${gameNumber})`);

  const frames = await apiGet(`/api/runs/${encodeURIComponent(runId)}/games/${gameNumber}/frames`);
  assert(Array.isArray(frames), "Expected frames array");
  console.log(`[smoke] replay frames ok (${frames.length} frames)`);
}

async function apiGet(path) {
  return apiRequest(path, "GET");
}

async function apiPost(path, body) {
  return apiRequest(path, "POST", body);
}

async function apiRequest(path, method, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const text = await response.text();
    const payload = text ? safeJsonParse(text) : null;
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} for ${path}: ${text || response.statusText}`);
    }
    return payload;
  } finally {
    clearTimeout(timeout);
  }
}

function safeJsonParse(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

main().catch((error) => {
  console.error(`[smoke] failed: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
