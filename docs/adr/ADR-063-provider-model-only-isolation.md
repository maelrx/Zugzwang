---
id: ADR-063
title: "Isolamento model-only obrigatório"
status: accepted
decision_owner: "Mestre Mael"
date: "2026-09-09"
source: "Pedido direto do operador; ZGW-0117"
---

# ADR-063 — Isolamento model-only obrigatório

Status: accepted. Date: 2026-09-09. Work order: ZGW-0117.
Authority: Mestre Mael explicitly required blocking arbitrary execution in every provider.

## Decision

All first-party adapters must expose model inference and inert chess proposals only.
Codex launches with user config/rules ignored, strict configuration, native shell,
MCP, web, apps, plugins, hooks and subagents disabled. Authentication remains local.
The installed CLI was tested against a fake Responses server: both requests had
`tools=[]`; an injected `exec_command` was refused and never executed.
OpenCode requires an acknowledged deny-all session policy before any prompt.
Antigravity CLI is unavailable because no verifiable tools-off mode exists.
Direct HTTP adapters never supply native executors. Typed execution receipts are
rejected at adapters and at the canonical RecordingBackend/Arena boundary;
failed wire evidence is retained, no move is committed, no retry follows security failure.
The kernel's typed chess broker remains available: board observations and model-only
search are declared H4 assistance; engine evaluations stay outside model context.

## Compatibility and limits

ProviderIsolationError is an additive SecurityError subclass (ZGZ-SECURITY-001,
retryability none); no serialized schema changes. Old manifests still parse, but
unsafe provider paths intentionally stop. Existing unisolated runs are not resumed.
This changes the execution condition: new runs use model-only/v1 and new identities.
Historical wins may select candidates but are not clean isolation baselines.
This boundary governs trusted first-party adapters and the verified CLI version;
it cannot prove an opaque remote provider's internal computation or safely execute
malicious third-party plugin code. Unknown CLI flags fail closed without fallback.

## Evidence

Private artifacts: out/guardrail-isolation-20260909; contract isolation tests,
canonical rejected-event evidence test, Arena no-commit test and real CLI injection.
