"""SQLAlchemy Core table definitions (design §11.3).

Rows never cross repository boundaries; repositories return domain DTOs.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

experiments = Table(
    "experiments",
    metadata,
    Column("experiment_id", String(32), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("source_manifest_artifact_id", String(128), nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("tags_json", JSON, nullable=False),
)

runs = Table(
    "runs",
    metadata,
    Column("run_id", String(32), primary_key=True),
    Column("experiment_id", String(32), nullable=True),
    Column("condition_id", String(32), nullable=False),
    Column("status", String(24), nullable=False),
    Column("resolved_manifest_artifact_id", String(128), nullable=True),
    Column("protocol_hash", String(64), nullable=False),
    Column("declared_assistance", String(8), nullable=False),
    Column("effective_assistance", String(8), nullable=True),
    Column("started_at", String(32), nullable=True),
    Column("finished_at", String(32), nullable=True),
    Column("failure_code", String(64), nullable=True),
    Column("projection_version", Integer, nullable=False, default=0),
)

episodes = Table(
    "episodes",
    metadata,
    Column("episode_id", String(32), primary_key=True),
    Column("run_id", String(32), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("task_type", String(128), nullable=False),
    Column("seed", BigInteger, nullable=False),
    Column("status", String(24), nullable=False),
    Column("outcome", String(32), nullable=True),
    Column("initial_state_artifact_id", String(128), nullable=True),
    Column("final_state_artifact_id", String(128), nullable=True),
    Column("effective_assistance", String(8), nullable=True),
    Column("config_json", JSON, nullable=True),
)

steps = Table(
    "steps",
    metadata,
    Column("step_id", String(32), primary_key=True),
    Column("episode_id", String(32), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("actor_id", String(128), nullable=False),
    Column("status", String(24), nullable=False),
    Column("observation_artifact_id", String(128), nullable=True),
    Column("action_json", JSON, nullable=True),
    Column("transition_artifact_id", String(128), nullable=True),
    Column("committed_at", String(32), nullable=True),
)

attempts = Table(
    "attempts",
    metadata,
    Column("attempt_id", String(32), primary_key=True),
    Column("step_id", String(32), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("request_artifact_id", String(128), nullable=True),
    Column("response_artifact_id", String(128), nullable=True),
    Column("failure_code", String(64), nullable=True),
    Column("outcome_unknown", Integer, nullable=False, default=0),
    Column("latency_ms", Integer, nullable=True),
    Column("usage_json", JSON, nullable=True),
    Column("cost_json", JSON, nullable=True),
)

events = Table(
    "events",
    metadata,
    Column("event_id", String(32), primary_key=True),
    Column("run_id", String(32), nullable=False),
    Column("episode_id", String(32), nullable=True),
    Column("step_id", String(32), nullable=True),
    Column("attempt_id", String(32), nullable=True),
    Column("stream_type", String(24), nullable=False),
    Column("stream_id", String(32), nullable=False),
    Column("sequence_no", Integer, nullable=False),
    Column("event_type", String(128), nullable=False),
    Column("event_version", Integer, nullable=False),
    Column("occurred_at", String(32), nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("artifact_refs_json", JSON, nullable=False),
    Column("trace_id", String(64), nullable=True),
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("artifact_id", String(128), primary_key=True),
    Column("algorithm", String(16), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("media_type", String(200), nullable=False),
    Column("compression", String(32), nullable=True),
    Column("relative_path", String(256), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("redaction_policy", String(32), nullable=True),
)

metric_observations = Table(
    "metric_observations",
    metadata,
    Column("metric_observation_id", String(32), primary_key=True),
    Column("run_id", String(32), nullable=False),
    Column("episode_id", String(32), nullable=True),
    Column("step_id", String(32), nullable=True),
    Column("metric_definition_id", String(128), nullable=False),
    Column("metric_version", String(16), nullable=False),
    Column("value_num", Float(), nullable=True),
    Column("value_text", Text, nullable=True),
    Column("value_json", JSON, nullable=True),
    Column("unit", String(32), nullable=False),
    Column("dimensions_json", JSON, nullable=False),
    Column("provenance_artifact_id", String(128), nullable=True),
    Column("evaluator_id", String(128), nullable=False),
    Column("evaluator_version", String(16), nullable=False),
)

budget_ledger = Table(
    "budget_ledger",
    metadata,
    Column("ledger_id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(32), nullable=False),
    Column("unit", String(32), nullable=False),
    Column("reserved", String(40), nullable=False),
    Column("used", String(40), nullable=False),
    Column("updated_at", String(32), nullable=False),
)

checkpoints = Table(
    "checkpoints",
    metadata,
    Column("checkpoint_id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(32), nullable=False),
    Column("stream_type", String(24), nullable=False),
    Column("stream_id", String(32), nullable=False),
    Column("sequence_committed", Integer, nullable=False),
    Column("state_artifact_id", String(128), nullable=True),
    Column("schema_version", String(32), nullable=False),
    Column("created_at", String(32), nullable=False),
)

TABLES = (
    experiments,
    runs,
    episodes,
    steps,
    attempts,
    events,
    artifacts,
    metric_observations,
    budget_ledger,
    checkpoints,
)
