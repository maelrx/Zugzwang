"""Local workspace layout (design §11.2).

SQLite WAL requires a local filesystem; the workspace is never shared across
hosts. This module owns paths and the ``init`` layout; it never owns SQL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zugzwang_core.domain.errors import ConfigurationError
from zugzwang_runtime.persistence.sqlite_policy import WalPolicy

WORKSPACE_DIRNAME = ".zugzwang"
DEFAULT_CONFIG_NAME = "config.toml"

SUBDIRS: tuple[str, ...] = (
    "objects",
    "runs",
    "cache",
    "tmp",
    "locks",
)

DEFAULT_CONFIG_TOML = """# Zugzwang workspace configuration (operational defaults only).
# Scientific defaults never hide here: anything that changes results goes
# into the ResolvedManifest (design §26.3).

[workspace]
data_dir = ".zugzwang"

[execution]
max_concurrent_episodes = 4

[logging]
format = "human"
level = "INFO"

[security]
allow_private_network = false
"""


def resolve_wal_policy(override: WalPolicy | None = None) -> WalPolicy:
    """Resolve the SQLite wal policy: explicit override > env > "enforce".

    ``ZUGZWANG_WAL_POLICY=ephemeral`` is an explicit operator decision for
    non-durable use (never a hidden default); anything else is an error.
    """
    if override is not None:
        return override
    value = os.environ.get("ZUGZWANG_WAL_POLICY", "enforce")
    if value not in ("enforce", "ephemeral"):
        raise ConfigurationError(
            f"invalid ZUGZWANG_WAL_POLICY {value!r}; expected 'enforce' or 'ephemeral'",
        )
    return value  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class Workspace:
    """Resolved paths for one local workspace.

    ``wal_policy`` selects the SQLite profile for this workspace: ``enforce``
    (default, durable: WAL requires an approved corrected release line) or
    ``ephemeral`` (explicit non-durable mode for throwaway fixtures/tests).
    """

    root: Path
    data_dir: Path
    wal_policy: WalPolicy = "enforce"

    @classmethod
    def discover(cls, start: Path | None = None) -> Workspace:
        """Find the workspace walking up from ``start`` (default cwd)."""
        current = (start or Path.cwd()).resolve()
        for candidate in (current, *current.parents):
            marker = candidate / WORKSPACE_DIRNAME
            if marker.is_dir():
                return cls(root=candidate, data_dir=marker, wal_policy=resolve_wal_policy())
        raise ConfigurationError(
            "no zugzwang workspace found; run 'zugzwang init' first",
            technical_context=f"searched up from {current}",
        )

    @classmethod
    def discover_optional(cls, start: Path | None = None) -> Workspace | None:
        try:
            return cls.discover(start)
        except ConfigurationError:
            return None

    @classmethod
    def from_root(cls, root: Path, wal_policy: WalPolicy | None = None) -> Workspace:
        return cls(
            root=root.resolve(),
            data_dir=(root / WORKSPACE_DIRNAME).resolve(),
            wal_policy=resolve_wal_policy(wal_policy),
        )

    @property
    def config_path(self) -> Path:
        return self.data_dir / DEFAULT_CONFIG_NAME

    def subdir(self, name: str) -> Path:
        if name not in SUBDIRS:
            raise ValueError(f"unknown workspace subdir {name!r}")
        return self.data_dir / name

    def run_dir(self, run_id: str) -> Path:
        return self.subdir("runs") / run_id

    def objects_dir(self) -> Path:
        return self.subdir("objects")

    def ensure_layout(self) -> tuple[Path, ...]:
        """Create missing workspace directories. Idempotent."""
        created: list[Path] = []
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for name in SUBDIRS:
            path = self.data_dir / name
            if not path.exists():
                path.mkdir(parents=True)
                created.append(path)
        config = self.config_path
        if not config.exists():
            config.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
            created.append(config)
        return tuple(created)


def load_config_toml(workspace: Workspace) -> dict[str, object]:
    import tomllib

    path = workspace.config_path
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(
            f"invalid workspace config {path}",
            technical_context=str(exc),
        ) from exc


def is_local_fs(workspace: Workspace) -> bool:
    """Best-effort check that the workspace is on a local filesystem."""
    try:
        st = os.stat(workspace.data_dir)
        return bool(st.st_dev)
    except OSError:
        return True
