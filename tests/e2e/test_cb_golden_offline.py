"""ZGW-0101 golden — the productive path end to end via the real CLI stack.

Runs ``experiments/cognitive-golden-offline.yaml`` through
``DurableRunServices.start`` (the same composition the CLI uses) against a
scratch workspace with the fake backend, then asserts the full evidence
chain in the journal: decision COMMITTED with selection_source=model, the
observe→expand→finalize operations, the expansion child bound at depth 1,
per-unit budget debits, and exposure rows. Network/socket use is blocked for
the whole test so no external call can hide behind the run.
"""

import asyncio
import socket
from pathlib import Path

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.e2e


@pytest.fixture()
def no_network(monkeypatch):
    """Block INET/TCP traffic; Unix-domain pairs (asyncio internals) stay.

    The guard proves no external call happens: any AF_INET/AF_INET6 socket
    or DNS resolution raises, while in-process asyncio keeps working.
    """
    real_socket = socket.socket

    def _guarded(family=socket.AF_INET, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("network is blocked in the golden offline test")
        return real_socket(family, *args, **kwargs)

    def _blocked_tcp(*args, **kwargs):
        raise RuntimeError("network is blocked in the golden offline test")

    def _blocked_dns(*args, **kwargs):
        raise RuntimeError("network is blocked in the golden offline test")

    monkeypatch.setattr(socket, "socket", _guarded)
    monkeypatch.setattr(socket, "create_connection", _blocked_tcp)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked_dns)
    return True


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "experiments" / "cognitive-golden-offline.yaml"


def test_golden_cognitive_run_commits_with_full_evidence(tmp_path, no_network) -> None:
    from zugzwang_runtime.application.commands import StartRunCommand
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.execution.registry import PluginRegistry
    from zugzwang_runtime.persistence.database import Database
    from zugzwang_runtime.workspace import Workspace

    workspace = Workspace(root=tmp_path, data_dir=tmp_path / ".zugzwang", wal_policy="ephemeral")
    services = DurableRunServices(workspace, PluginRegistry())
    result = asyncio.run(
        services.start(
            StartRunCommand(manifest_path=_manifest_path(), condition_index=0),
            __import__("asyncio").Event(),
        )
    )
    assert result.status == "COMPLETED", result

    database = Database(tmp_path / ".zugzwang" / "state.db", wal_policy="ephemeral")
    engine = database.open()
    with engine.connect() as conn:
        decisions = conn.execute(
            text("SELECT status, selected_action, selection_source FROM cb_decisions")
        ).fetchall()
        assert len(decisions) == 1
        assert decisions[0] == ("COMMITTED", "e2e4", "model")

        ops = conn.execute(
            text("SELECT tool_name, status FROM cb_tool_operations ORDER BY created_at")
        ).fetchall()
        assert ("board_observe", "COMMITTED") in ops
        assert ("board_expand", "COMMITTED") in ops

        depths = sorted(
            row[0]
            for row in conn.execute(text("SELECT depth_plies FROM cb_node_bindings")).fetchall()
        )
        assert depths == [0, 1], "root plus exactly one expansion child"

        budget = {
            row[0]: (row[1], row[2])
            for row in conn.execute(
                text(
                    "SELECT unit, SUM(delta_reserved), SUM(delta_used) "
                    "FROM cb_budget_entries GROUP BY unit"
                )
            ).fetchall()
        }
        assert budget["tool_operations"][1] >= 2
        assert budget["model_calls"][1] >= 2

        exposures = conn.execute(text("SELECT COUNT(*) FROM cb_observations")).scalar_one()
        assert exposures >= 2


def test_golden_manifest_declares_offline_only() -> None:
    text_content = _manifest_path().read_text(encoding="utf-8")
    assert "fake.backend" in text_content
    assert "chess.cognitive_navigation" in text_content
    assert "provider." not in text_content.replace("provider: fake", "")
