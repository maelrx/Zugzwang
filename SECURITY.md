# Security policy

## Supported versions

No runtime release exists yet. This foundation corpus is documentation-only.

## Reporting

Do not file a public issue for vulnerabilities involving secrets, provider credentials, arbitrary code execution, artifact disclosure, path traversal, plugin trust or evidence corruption. Contact the repository owner through a private GitHub security advisory once the repository is active.

## Threat priorities

- provider/API secret leakage;
- raw prompt/response disclosure;
- malicious plugin import or side effects;
- path traversal/symlink attacks in bundles and CAS;
- command injection in UCI/process supervision;
- tampering with events, manifests or metric provenance;
- resource exhaustion and unbounded spend;
- specification gaming through filesystem/process access.

## Design posture

The v0.1 kernel avoids arbitrary code tools, uses explicit process/network boundaries, local plugin trust, bounded budgets and immutable evidence. Security controls are documented in `docs/architecture/SECURITY_THREAT_MODEL.md`.
