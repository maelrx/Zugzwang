# Security threat model

## Assets

- provider secrets;
- raw prompts/responses;
- proprietary outputs;
- experiment integrity;
- engine binaries;
- datasets;
- bundles and signatures;
- local filesystem;
- cost budget.

## Adversaries

- malicious or compromised plugin;
- hostile model output;
- tampered imported bundle;
- poisoned dataset/knowledge packet;
- provider drift;
- supply-chain package;
- accidental operator misconfiguration.

## Threats

### Secret leakage

Mitigation: env/keyring adapters, redaction, never serialize secret values, bundle scanner.

### Arbitrary code execution

No eval/exec, no model-generated shell, no unrestricted Python tools.

### Path traversal

Artifact and bundle paths are normalized, rooted and hash-validated.

### Prompt/tool injection

Knowledge packets are data; tool authority is manifest-controlled; model cannot create new permissions.

### Engine tampering

Hash binary, isolate working directory, resource-limit process, audit UCI transcript.

### Bundle forgery

Checksums, schema validation, optional signatures later, immutable import namespace.

### Cost runaway

Hard budgets, rate limits, projected stop, no hidden retry/fallback.

### Specification gaming

Environment state and outcome are canonical. Win is accepted only through a legal trajectory.

### SQLite corruption

Fixed SQLite runtime, one writer, backups, integrity checks, WAL policy.

### Plugin compromise

Allowlist in CI, no auto-install, descriptor and license capture, future process isolation if needed.

## Security report

See root [SECURITY.md](../../SECURITY.md).
