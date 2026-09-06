"""CognitiveBoard CB-M1: decision journal tables (PRD §23.1/§23.2, ZGW-0091).

Intermediate CB-M1 subset: state snapshots v2, decisions, node bindings,
rounds, provider links, idempotent tool operations, observations and the
append-only budget journal. Columns and triggers that depend on CB-M2/M3
(memory snapshots, skill sets) are intentionally absent — the code above this
schema must not presume future tables (PRD §23.1).

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_DDL = [
    # -- state snapshots v2 --------------------------------------------------
    """
    CREATE TABLE cb_state_snapshots (
        state_key TEXT NOT NULL PRIMARY KEY,
        state_schema_version TEXT NOT NULL,
        rules_version TEXT NOT NULL,
        variant TEXT NOT NULL CHECK (variant = 'standard'),
        position_key TEXT NOT NULL,
        history_completeness TEXT NOT NULL CHECK (history_completeness IN ('complete','from_anchor')),
        state_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX cb_state_position_idx ON cb_state_snapshots(position_key)",
    """
    CREATE TRIGGER cb_state_snapshot_no_update BEFORE UPDATE ON cb_state_snapshots
    BEGIN SELECT RAISE(ABORT, 'state snapshots are immutable'); END;
    """,
    """
    CREATE TRIGGER cb_state_snapshot_no_delete BEFORE DELETE ON cb_state_snapshots
    BEGIN SELECT RAISE(ABORT, 'state snapshots are immutable'); END;
    """,
    # -- decisions (intermediate: no CB-M2/M3 snapshot columns) ---------------
    """
    CREATE TABLE cb_decisions (
        decision_id TEXT NOT NULL PRIMARY KEY,
        step_id TEXT NOT NULL REFERENCES steps(step_id),
        decision_ordinal INTEGER NOT NULL CHECK (decision_ordinal >= 0),
        search_session_id TEXT NOT NULL UNIQUE REFERENCES search_sessions(search_session_id),
        root_state_key TEXT NOT NULL REFERENCES cb_state_snapshots(state_key),
        status TEXT NOT NULL CHECK (status IN
            ('PREPARING','READY','ACTIVE','OUTCOME_UNKNOWN','PAUSED','SELECTED','COMMITTED','FAILED','CANCELLED')),
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        interaction_mode TEXT NOT NULL CHECK (interaction_mode IN ('native_tools','json_commands')),
        policy_hash TEXT NOT NULL,
        config_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        next_round_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (next_round_ordinal >= 0),
        checkpoint_artifact_id TEXT REFERENCES artifacts(artifact_id),
        selected_action TEXT,
        selection_source TEXT CHECK (selection_source IN ('model','runtime_fallback')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
        created_at TEXT NOT NULL,
        finished_at TEXT,
        UNIQUE(step_id, decision_ordinal),
        CHECK (status NOT IN ('SELECTED','COMMITTED') OR
            (selected_action IS NOT NULL AND selection_source IS NOT NULL))
    )
    """,
    "CREATE INDEX cb_decisions_step_idx ON cb_decisions(step_id, status)",
    """
    CREATE TRIGGER cb_decision_identity_fixed BEFORE UPDATE ON cb_decisions
    WHEN NEW.root_state_key <> OLD.root_state_key OR NEW.policy_hash <> OLD.policy_hash
     OR NEW.search_session_id <> OLD.search_session_id OR NEW.step_id <> OLD.step_id
     OR NEW.config_artifact_id <> OLD.config_artifact_id
    BEGIN SELECT RAISE(ABORT, 'decision identity and policy are immutable'); END;
    """,
    # -- node bindings --------------------------------------------------------
    """
    CREATE TABLE cb_node_bindings (
        decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        node_id TEXT NOT NULL REFERENCES search_nodes(node_id),
        state_key TEXT NOT NULL REFERENCES cb_state_snapshots(state_key),
        depth_plies INTEGER NOT NULL CHECK (depth_plies >= 0),
        created_sequence INTEGER NOT NULL CHECK (created_sequence >= 0),
        PRIMARY KEY(decision_id, node_id)
    )
    """,
    "CREATE INDEX cb_node_state_idx ON cb_node_bindings(state_key)",
    """
    CREATE TRIGGER cb_node_scope_guard BEFORE INSERT ON cb_node_bindings
    WHEN (SELECT search_session_id FROM search_nodes WHERE node_id = NEW.node_id)
     <> (SELECT search_session_id FROM cb_decisions WHERE decision_id = NEW.decision_id)
    BEGIN SELECT RAISE(ABORT, 'node belongs to another search session'); END;
    """,
    """
    CREATE TRIGGER cb_node_binding_no_update BEFORE UPDATE ON cb_node_bindings
    BEGIN SELECT RAISE(ABORT, 'node binding is immutable'); END;
    """,
    # -- rounds ---------------------------------------------------------------
    """
    CREATE TABLE cb_rounds (
        round_id TEXT NOT NULL PRIMARY KEY,
        decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
        purpose TEXT NOT NULL CHECK (purpose IN ('explore','finalize','repair')),
        status TEXT NOT NULL CHECK (status IN
            ('PREPARED','REQUEST_PENDING','RESPONSE_COMMITTED','TOOLS_COMMITTED','OUTCOME_UNKNOWN','FAILED')),
        context_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        response_artifact_id TEXT REFERENCES artifacts(artifact_id),
        checkpoint_artifact_id TEXT REFERENCES artifacts(artifact_id),
        created_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE(decision_id, ordinal),
        UNIQUE(round_id, decision_id)
    )
    """,
    """
    CREATE TRIGGER cb_round_identity_fixed BEFORE UPDATE ON cb_rounds
    WHEN NEW.decision_id <> OLD.decision_id OR NEW.ordinal <> OLD.ordinal
     OR NEW.context_artifact_id <> OLD.context_artifact_id
    BEGIN SELECT RAISE(ABORT, 'round identity and submitted context are immutable'); END;
    """,
    # -- provider links -------------------------------------------------------
    """
    CREATE TABLE cb_provider_links (
        round_id TEXT NOT NULL,
        decision_id TEXT NOT NULL,
        attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
        transport_ordinal INTEGER NOT NULL CHECK (transport_ordinal >= 0),
        route_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        PRIMARY KEY(round_id, attempt_id),
        UNIQUE(attempt_id),
        UNIQUE(round_id, transport_ordinal),
        FOREIGN KEY(round_id, decision_id) REFERENCES cb_rounds(round_id, decision_id)
    )
    """,
    """
    CREATE TRIGGER cb_provider_step_guard BEFORE INSERT ON cb_provider_links
    WHEN (SELECT step_id FROM attempts WHERE attempt_id = NEW.attempt_id)
     <> (SELECT step_id FROM cb_decisions WHERE decision_id = NEW.decision_id)
    BEGIN SELECT RAISE(ABORT, 'provider attempt belongs to another step'); END;
    """,
    """
    CREATE TRIGGER cb_provider_link_no_update BEFORE UPDATE ON cb_provider_links
    BEGIN SELECT RAISE(ABORT, 'provider links are immutable'); END;
    """,
    # -- idempotent tool operations ------------------------------------------
    """
    CREATE TABLE cb_tool_operations (
        operation_id TEXT NOT NULL PRIMARY KEY,
        decision_id TEXT NOT NULL,
        round_id TEXT NOT NULL,
        provider_tool_call_id TEXT NOT NULL,
        command_ordinal INTEGER NOT NULL CHECK (command_ordinal >= 0),
        idempotency_key TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        arguments_hash TEXT NOT NULL,
        arguments_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        status TEXT NOT NULL CHECK (status IN ('PREPARED','COMMITTED','REJECTED','FAILED')),
        result_artifact_id TEXT REFERENCES artifacts(artifact_id),
        error_code TEXT,
        logical_ops INTEGER NOT NULL DEFAULT 1 CHECK (logical_ops >= 0),
        physical_rules_queries INTEGER NOT NULL DEFAULT 0 CHECK (physical_rules_queries >= 0),
        new_nodes INTEGER NOT NULL DEFAULT 0 CHECK (new_nodes >= 0),
        elapsed_us INTEGER CHECK (elapsed_us >= 0),
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(round_id, decision_id) REFERENCES cb_rounds(round_id, decision_id),
        UNIQUE(decision_id, idempotency_key),
        UNIQUE(round_id, provider_tool_call_id),
        UNIQUE(round_id, command_ordinal),
        UNIQUE(operation_id, decision_id),
        CHECK (status NOT IN ('COMMITTED','REJECTED') OR result_artifact_id IS NOT NULL)
    )
    """,
    "CREATE INDEX cb_tool_decision_status_idx ON cb_tool_operations(decision_id, status)",
    """
    CREATE TRIGGER cb_operation_identity_fixed BEFORE UPDATE ON cb_tool_operations
    WHEN NEW.decision_id <> OLD.decision_id OR NEW.round_id <> OLD.round_id
     OR NEW.tool_name <> OLD.tool_name OR NEW.arguments_hash <> OLD.arguments_hash
     OR NEW.idempotency_key <> OLD.idempotency_key
    BEGIN SELECT RAISE(ABORT, 'tool operation identity is immutable'); END;
    """,
    """
    CREATE TRIGGER cb_operation_committed_fixed BEFORE UPDATE ON cb_tool_operations
    WHEN OLD.status IN ('COMMITTED','REJECTED')
    BEGIN SELECT RAISE(ABORT, 'settled tool operations are immutable'); END;
    """,
    # -- observations ---------------------------------------------------------
    """
    CREATE TABLE cb_observations (
        observation_id TEXT NOT NULL PRIMARY KEY,
        decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        node_id TEXT NOT NULL,
        round_id TEXT,
        operation_id TEXT,
        kind TEXT NOT NULL CHECK (kind IN ('initial','view','inspect','expand','compare','memory','analysis')),
        payload_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        semantic_hash TEXT NOT NULL,
        policy_hash TEXT NOT NULL,
        exposure_sequence INTEGER NOT NULL CHECK (exposure_sequence >= 0),
        available_before_selection INTEGER NOT NULL CHECK (available_before_selection IN (0,1)),
        created_at TEXT NOT NULL,
        FOREIGN KEY(decision_id, node_id) REFERENCES cb_node_bindings(decision_id, node_id),
        FOREIGN KEY(round_id, decision_id) REFERENCES cb_rounds(round_id, decision_id),
        FOREIGN KEY(operation_id, decision_id) REFERENCES cb_tool_operations(operation_id, decision_id),
        UNIQUE(decision_id, exposure_sequence)
    )
    """,
    "CREATE INDEX cb_observation_timeline_idx ON cb_observations(decision_id, exposure_sequence)",
    """
    CREATE TRIGGER cb_observation_no_update BEFORE UPDATE ON cb_observations
    BEGIN SELECT RAISE(ABORT, 'observations are immutable'); END;
    """,
    """
    CREATE TRIGGER cb_observation_no_delete BEFORE DELETE ON cb_observations
    BEGIN SELECT RAISE(ABORT, 'observations are immutable'); END;
    """,
    # -- budget journal (append-only) -----------------------------------------
    """
    CREATE TABLE cb_budget_reservations (
        reservation_id TEXT NOT NULL PRIMARY KEY,
        decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        owner_kind TEXT NOT NULL CHECK (owner_kind IN ('provider_attempt','tool_operation','finalization')),
        owner_id TEXT NOT NULL,
        unit TEXT NOT NULL CHECK (unit IN
            ('model_calls','input_tokens','output_tokens','tool_operations','rules_queries',
             'transition_attempts','unique_nodes','context_bytes','wall_time_ms','cost_microusd')),
        amount INTEGER NOT NULL CHECK (amount >= 0),
        status TEXT NOT NULL CHECK (status IN ('RESERVED','SETTLED','RELEASED','UNKNOWN')),
        created_at TEXT NOT NULL,
        settled_at TEXT,
        UNIQUE(decision_id, owner_kind, owner_id, unit)
    )
    """,
    "CREATE INDEX cb_reservation_status_idx ON cb_budget_reservations(decision_id, unit, status)",
    """
    CREATE TABLE cb_budget_entries (
        entry_id TEXT NOT NULL PRIMARY KEY,
        decision_id TEXT NOT NULL REFERENCES cb_decisions(decision_id),
        reservation_id TEXT REFERENCES cb_budget_reservations(reservation_id),
        sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
        event_kind TEXT NOT NULL CHECK (event_kind IN ('reserve','settle','release','uncertain','adjustment')),
        unit TEXT NOT NULL,
        delta_reserved INTEGER NOT NULL,
        delta_used INTEGER NOT NULL,
        evidence_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        created_at TEXT NOT NULL,
        UNIQUE(decision_id, sequence_no)
    )
    """,
    """
    CREATE TRIGGER cb_budget_entry_guard BEFORE INSERT ON cb_budget_entries
    WHEN NEW.reservation_id IS NOT NULL AND
     ((SELECT decision_id FROM cb_budget_reservations WHERE reservation_id = NEW.reservation_id) <> NEW.decision_id
     OR (SELECT unit FROM cb_budget_reservations WHERE reservation_id = NEW.reservation_id) <> NEW.unit)
    BEGIN SELECT RAISE(ABORT, 'reservation scope or unit mismatch'); END;
    """,
    """
    CREATE TRIGGER cb_budget_no_update BEFORE UPDATE ON cb_budget_entries
    BEGIN SELECT RAISE(ABORT, 'budget journal is append-only'); END;
    """,
    """
    CREATE TRIGGER cb_budget_no_delete BEFORE DELETE ON cb_budget_entries
    BEGIN SELECT RAISE(ABORT, 'budget journal is append-only'); END;
    """,
]

_DROP_ORDER = [
    "cb_budget_entries",
    "cb_budget_reservations",
    "cb_observations",
    "cb_tool_operations",
    "cb_provider_links",
    "cb_rounds",
    "cb_node_bindings",
    "cb_decisions",
    "cb_state_snapshots",
]


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)


def downgrade() -> None:
    """Feature rollback. Refuses to drop when decision data exists (PRD §23.3:
    no automatic DROP TABLE back to baseline while new runs are present)."""
    bind = op.get_bind()
    decision_rows = bind.execute(sa.text("SELECT COUNT(*) FROM cb_decisions")).scalar()
    if decision_rows:
        raise RuntimeError(
            "refusing destructive rollback: cb_decisions holds "
            f"{decision_rows} row(s); archive or clear decision data first"
        )
    for table in _DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
