# Foundation validation report

**Artifact:** `zugzwang-engine-foundation`  
**Version:** `0.1.0`  
**Lifecycle phase:** `pre-scaffold`  
**Validated on:** 2026-08-12 (America/Sao_Paulo)  
**Validator:** `scripts/validate_foundation.py`

## Result

```text
PASS 10  WARN 0  ERROR 0
  ✓ required files
  ✓ JSON parsed: 7
  ✓ YAML parsed: 17
  ✓ JSON Schemas checked: 6
  ✓ ADRs validated: 45
  ✓ skills validated: 20
  ✓ local markdown links checked: 231
  ✓ no unexpected control characters
  ✓ decision gates validated: 12
  ✓ license gate respected: no LICENSE before decision
```

## Additional packaging checks

- Python source under `scripts/` compiles successfully.
- Every draft JSON Schema validates against Draft 2020-12.
- Included schema examples validate against their declared schemas.
- ADR identifiers are unique and their minimum metadata is present.
- Every Agent Skill has valid frontmatter, an exact directory/name match, workflow guidance, verification steps, and stop conditions.
- The source archive preserves the operator-provided scientific dossier and the previous greenfield design byte-for-byte, with SHA-256 values recorded in `archive/source-material/MANIFEST.yaml`.
- A `LICENSE` file, active `pyproject.toml`, and `uv.lock` are intentionally absent until the corresponding human decision gates are ratified.

## Scope of this validation

A passing report establishes the internal integrity of the **documentation-first foundation pack**. It does not claim that a Zugzwang runtime, provider adapter, database migration, chess environment, benchmark result, or release artifact has already been implemented or executed.

## Reproduction

From the repository root:

```bash
python scripts/validate_foundation.py
python -m compileall -q scripts
```

For implementation work, ratify the blocking gates in `docs/decisions/DECISIONS.yaml`, update their linked ADRs, and then run:

```bash
python scripts/validate_foundation.py --strict-decisions
```
