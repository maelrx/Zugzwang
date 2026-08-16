# Foundation scripts

These scripts validate and maintain the documentation-first repository without requiring the future runtime.

```bash
python scripts/validate_foundation.py
python scripts/validate_foundation.py --strict
python scripts/validate_foundation.py --strict-decisions
python scripts/decision_status.py
python scripts/new_adr.py --title "..."
python scripts/new_experiment.py --id EXP-XXX --title "..."
```

`--strict` enables optional YAML/JSON Schema validation when dependencies are available and treats warnings as failures. Default mode uses Python stdlib and remains suitable for the pre-scaffold CI.
