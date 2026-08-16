"""Architecture tests: forbidden imports per DEPENDENCY_RULES.md.

These tests fail the build if a forbidden dependency appears in package
source (ADR-006/§7.1). They scan AST imports, not runtime state.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN: dict[str, dict[str, tuple[str, ...]]] = {
    "packages/zugzwang-core": {
        "packages/zugzwang-core/src": (
            "typer",
            "rich",
            "sqlalchemy",
            "alembic",
            "pydantic_ai",
            "chess",
            "stockfish",
            "httpx",
            "duckdb",
            "pyarrow",
            "fastapi",
            "zugzwang_runtime",
            "zugzwang_chess",
            "zugzwang_cli",
        ),
    },
    "packages/zugzwang-chess": {
        "packages/zugzwang-chess/src": (
            "typer",
            "sqlalchemy",
            "zugzwang_runtime",
            "zugzwang_cli",
        ),
    },
    "packages/zugzwang-runtime": {
        "packages/zugzwang-runtime/src": (
            "typer",
            "rich",
            "zugzwang_cli",
            "fastapi",
        ),
    },
    "packages/zugzwang-cli": {
        "packages/zugzwang-cli/src": (
            "sqlalchemy",
            "alembic",
        ),
    },
    "plugins": {
        "plugins": (
            "zugzwang_runtime.persistence",
            "zugzwang_runtime.execution.registry",
        ),
    },
}

PLUGIN_PRIVATE_RUNTIME = (
    "zugzwang_runtime.persistence",
    "zugzwang_runtime.execution",
)


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _collect_cases():
    cases: list[tuple[str, Path, str]] = []
    for package_dir, rule in FORBIDDEN.items():
        for scan_root, forbidden in rule.items():
            root = REPO_ROOT / scan_root
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                for module in _imported_modules(path):
                    if module in forbidden:
                        cases.append((package_dir, path, module))
    return cases


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("package_dir", "path", "module"),
    _collect_cases(),
)
def test_no_forbidden_imports(package_dir: str, path: Path, module: str) -> None:
    pytest.fail(f"{package_dir}: {path} imports forbidden module {module!r}")


@pytest.mark.architecture
def test_core_has_no_io_or_provider_imports() -> None:
    root = REPO_ROOT / "packages/zugzwang-core/src"
    all_modules = {module for path in root.rglob("*.py") for module in _imported_modules(path)}
    forbidden = {
        "typer",
        "sqlalchemy",
        "pydantic_ai",
        "httpx",
        "duckdb",
        "chess",
        "fastapi",
    }
    violations = all_modules & forbidden
    assert not violations, f"core imports forbidden modules: {sorted(violations)}"


@pytest.mark.architecture
def test_plugins_do_not_import_private_runtime() -> None:
    root = REPO_ROOT / "plugins"
    for path in root.rglob("*.py"):
        for module in _imported_modules(path):
            if any(module.startswith(prefix) for prefix in PLUGIN_PRIVATE_RUNTIME):
                pytest.fail(f"plugin {path} imports private runtime module {module!r}")


@pytest.mark.architecture
def test_core_depends_only_on_allowed_distributions() -> None:
    import tomllib

    pyproject = REPO_ROOT / "packages/zugzwang-core/pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps = [d.split(">=")[0].split("==")[0].split("[")[0] for d in data["project"]["dependencies"]]
    assert deps == ["pydantic"], f"core dependencies must be only pydantic, got {deps}"
