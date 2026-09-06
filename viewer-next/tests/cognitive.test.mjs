import test from 'node:test';
import assert from 'node:assert/strict';
import { loadBundle, parseSnapshot, SNAPSHOT_SCHEMA } from '../src/lib/cognitive.ts';

const snapshot = () => ({
  schema_version: SNAPSHOT_SCHEMA,
  decision_id: 'dec-cog-0001',
  status: 'COMMITTED',
  selected_action: 'e2e4',
  next_round_ordinal: 4,
  operations_settled: 3,
  operations_open: [],
  exposure_watermark: 3,
  budget_balance: { tool_operations: { reserved: 32, used: 3, remaining: 29 } },
  real_state: {
    status: 'COMMITTED',
    selected_action: 'e2e4',
    operations_settled: 3,
    operations_open: [],
    exposure_watermark: 3,
  },
  focus: { node_id: 'node-root', bound_nodes: ['node-root', 'node_child'] },
  eligible_memories: [{ memory_id: 'mem-w-r1', eligibility_reason: 'eligible-scope-partition-validity' }],
  audit: {
    decision_id: 'dec-cog-0001',
    status: 'COMMITTED',
    selected_action: 'e2e4',
    operations: [
      { operation_id: 'op-1', tool: 'board_observe', status: 'COMMITTED', error_code: null, result_artifact_id: 'sha256:aaa' },
      { operation_id: 'op-2', tool: 'board_expand', status: 'COMMITTED', error_code: null, result_artifact_id: 'sha256:bbb' },
    ],
    observations: 2,
    exposure_watermark: 2,
    artifacts_verified: 2,
    artifacts_failed: [],
  },
  mode: 'post_hoc',
  engine: null,
});

test('parseSnapshot accepts a real exporter snapshot', () => {
  const parsed = parseSnapshot(snapshot());
  assert.equal(parsed.decision_id, 'dec-cog-0001');
  assert.equal(parsed.audit.operations.length, 2);
  assert.equal(parsed.focus.bound_nodes.length, 2);
});

test('parseSnapshot refuses live mode and engine references', () => {
  assert.throws(() => parseSnapshot({ ...snapshot(), mode: 'live' }), /post-hoc/);
  assert.throws(() => parseSnapshot({ ...snapshot(), engine: { stockfish: true } }), /engine/);
  assert.throws(() => parseSnapshot({ ...snapshot(), schema_version: 'other/v9' }), /schema/);
  assert.throws(() => parseSnapshot({ ...snapshot(), audit: { operations: 'nope' } }), /operations/);
});

test('loadBundle reads a bundle of decisions and a lone snapshot', () => {
  const two = loadBundle({ decisions: [snapshot(), { ...snapshot(), decision_id: 'dec-cog-0002' }] });
  assert.equal(two.length, 2);
  assert.equal(two[1].decision_id, 'dec-cog-0002');
  const lone = loadBundle(snapshot());
  assert.equal(lone.length, 1);
});

test('timeline keyboard contract: handlers exist for ArrowUp/Down, j/k, Enter', async () => {
  const source = await import('node:fs').then(fs => fs.readFileSync(new URL('../src/components/CognitiveTimeline.tsx', import.meta.url), 'utf8'));
  for (const key of ['ArrowDown', 'ArrowUp', '"j"', '"k"', '"Enter"']) assert.ok(source.includes(key), `missing ${key}`);
  assert.ok(source.includes('data-testid="cognitive-timeline"'));
  assert.ok(source.includes('cognitive-op-'));
});
