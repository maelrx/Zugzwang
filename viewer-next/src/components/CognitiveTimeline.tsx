/**
 * Causal decision timeline (CB-WO-10, ZGW-0097).
 *
 * Renders one post-hoc cognitive snapshot: status vs focus, tool operations
 * with envelope references, budget balance and memory-free audit counts.
 * Keyboard: ArrowUp/ArrowDown (or j/k) move the focus row; Enter toggles
 * detail. No fetch, no engine, no write-back — dead data only.
 */
import { useCallback, useEffect, useState } from "react";
import type { CognitiveOperation, CognitiveSnapshot } from "../lib/cognitive";

interface Props {
  snapshot: CognitiveSnapshot;
}

function opLabel(op: CognitiveOperation): string {
  const tail = op.error_code ? ` (${op.error_code})` : "";
  return `${op.tool} · ${op.status}${tail}`;
}

export default function CognitiveTimeline({ snapshot }: Props): JSX.Element {
  const ops = snapshot.audit.operations;
  const [focus, setFocus] = useState(0);
  const [open, setOpen] = useState<Record<number, boolean>>({});

  const move = useCallback(
    (delta: number) => {
      setFocus((prev) => {
        if (ops.length === 0) return 0;
        const next = prev + delta;
        return Math.min(Math.max(next, 0), ops.length - 1);
      });
    },
    [ops.length],
  );

  const toggle = useCallback(() => {
    setOpen((prev) => ({ ...prev, [focus]: !prev[focus] }));
  }, [focus]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === "ArrowDown" || event.key === "j") {
        event.preventDefault();
        move(1);
      } else if (event.key === "ArrowUp" || event.key === "k") {
        event.preventDefault();
        move(-1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, toggle]);

  const units = Object.entries(snapshot.budget_balance);

  return (
    <section aria-label="Causal decision timeline" data-testid="cognitive-timeline">
      <header>
        <h2>
          {snapshot.decision_id} · {snapshot.status}
        </h2>
        <p>
          focus exposure {snapshot.exposure_watermark} · settled {snapshot.operations_settled}
          {snapshot.selected_action ? ` · selected ${snapshot.selected_action}` : ""}
        </p>
      </header>
      <section aria-label="Real state versus focus">
        <h3>real state vs focus</h3>
        <dl>
          <dt>real status</dt>
          <dd>{snapshot.real_state.status}</dd>
          <dt>focus node</dt>
          <dd>{snapshot.focus.node_id ?? "none"}</dd>
          <dt>bound nodes</dt>
          <dd>{snapshot.focus.bound_nodes.join(", ") || "none"}</dd>
        </dl>
      </section>
      <ol>
        {ops.map((op, index) => (
          <li
            key={op.operation_id}
            aria-current={index === focus ? "true" : undefined}
            data-testid={`cognitive-op-${index}`}
          >
            <button type="button" onClick={() => setFocus(index)} onDoubleClick={toggle}>
              {opLabel(op)}
            </button>
            {open[index] ? (
              <dl>
                <dt>operation_id</dt>
                <dd>{op.operation_id}</dd>
                <dt>result artifact</dt>
                <dd>{op.result_artifact_id ?? "none"}</dd>
                <dt>artifact verified</dt>
                <dd>{String(op.artifact_verified ?? "unknown")}</dd>
              </dl>
            ) : null}
          </li>
        ))}
      </ol>
      {snapshot.eligible_memories.length > 0 ? (
        <section aria-label="Eligible memories">
          <h3>eligible memories</h3>
          <ul>
            {snapshot.eligible_memories.map((memory) => (
              <li key={memory.memory_id}>
                {memory.memory_id} · {memory.eligibility_reason}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {units.length > 0 ? (
        <table aria-label="Budget balance">
          <thead>
            <tr>
              <th>unit</th>
              <th>reserved</th>
              <th>used</th>
              <th>remaining</th>
            </tr>
          </thead>
          <tbody>
            {units.map(([unit, balance]) => (
              <tr key={unit}>
                <td>{unit}</td>
                <td>{balance.reserved}</td>
                <td>{balance.used}</td>
                <td>{balance.remaining}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
