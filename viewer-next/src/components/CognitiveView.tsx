/**
 * Cognitive decisions index (CB-WO-10 remount, ZGW-0101).
 *
 * Lists every post-hoc decision snapshot from /data/cognitive.json and
 * mounts CognitiveTimeline for the selected one. Live match-desk data and
 * post-hoc causal analysis stay on separate routes by design.
 */
import { useState } from "react";
import CognitiveTimeline from "./CognitiveTimeline";
import { useCognitiveBundle } from "../lib/useCognitiveBundle";

export function CognitiveView() {
  const { snapshots, loading, error, reload } = useCognitiveBundle(15000);
  const [selected, setSelected] = useState(0);

  if (loading && !snapshots) {
    return (
      <div className="loading-state" role="status" aria-label="Carregando decisões">
        <div className="skeleton skeleton-title" />
        {[1, 2, 3].map((n) => (
          <div key={n} className="skeleton skeleton-row" />
        ))}
      </div>
    );
  }

  if (error && !snapshots) {
    return (
      <div className="empty-state">
        <h1>Nenhum bundle cognitivo</h1>
        <p>
          Gere <code>cognitive.json</code> com <code>scripts/build_cognitive_viewer.py</code> e
          publique em <code>public/data/</code>. Detalhe: {error}
        </p>
        <button className="button primary" type="button" onClick={() => void reload()}>
          Tentar novamente
        </button>
      </div>
    );
  }

  const list = snapshots ?? [];
  const current = list[Math.min(selected, Math.max(list.length - 1, 0))];

  return (
    <div>
      <div className="page-heading detail-heading">
        <div>
          <h1>Decisões cognitivas</h1>
          <p className="lead">
            {list.length} {list.length === 1 ? "decisão pós-hoc" : "decisões pós-hoc"} · dados
            mortos, sem engine
          </p>
        </div>
      </div>
      {list.length === 0 ? (
        <div className="empty-state">
          <h1>Bundle vazio</h1>
          <p>O bundle não contém decisões. Exporte ao menos uma decisão.</p>
        </div>
      ) : (
        <>
          <nav className="detail-tabs" aria-label="Decisões">
            {list.map((snap, index) => (
              <button
                key={snap.decision_id}
                type="button"
                onClick={() => setSelected(index)}
                aria-current={snap === current ? "page" : undefined}
              >
                {snap.decision_id} · {snap.status}
              </button>
            ))}
          </nav>
          {current ? <CognitiveTimeline key={current.decision_id} snapshot={current} /> : null}
        </>
      )}
    </div>
  );
}
