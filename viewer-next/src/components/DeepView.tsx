import { useMemo, useState } from "react";
import type { Run } from "@/lib/types";
import { conditionLabel, modelLabel, runState } from "@/lib/presentation";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";
export function DeepView({ run }: { run: Run }) {
  const [query, setQuery] = useState("");
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [limit, setLimit] = useState(30);
  const events = useMemo(() => [...(run.events ?? [])].reverse().filter(e => (!errorsOnly || /failed|error|timeout|rejected|violation/.test(e.type)) && (!query || e.type.toLowerCase().includes(query.toLowerCase()))), [run.events, query, errorsOnly]);
  const state = runState(run);
  return <div className="evidence-view">
    {state.label === "Revisar status" && <div className="notice"><Icon name="alert"/><div><strong>Divergência nos registros</strong><p>{state.detail} Os valores originais estão preservados abaixo.</p></div></div>}
    <section className="surface"><div className="section-heading"><div><h2>Identidade e proveniência</h2><p>O contexto registrado desta execução.</p></div><CopyButton text={run.id} label="Copiar ID"/></div><dl className="facts-grid provenance-grid">
      <div><dt>Modelo</dt><dd>{modelLabel(run)}</dd></div><div><dt>Condição</dt><dd>{conditionLabel(run)}</dd></div><div><dt>Status do run</dt><dd>{run.status}</dd></div><div><dt>Status dos episódios</dt><dd>{run.episodes.map(e => e.status).join(" · ") || "Não informado"}</dd></div><div><dt>Assistência declarada</dt><dd>{run.declaredAssistance ?? "Não informada"}</dd></div><div><dt>Assistência efetiva</dt><dd>{run.effectiveAssistance ?? "Não informada"}</dd></div><div><dt>Início</dt><dd>{run.startedAt ? new Date(run.startedAt).toLocaleString("pt-BR") : "Não informado"}</dd></div><div><dt>Fim</dt><dd>{run.finishedAt ? new Date(run.finishedAt).toLocaleString("pt-BR") : "Não informado"}</dd></div>
    </dl><div className="hash-field"><span className="quiet-label">Hash do protocolo</span><code>{run.protocolHash ?? "Não informado nesta leitura"}</code>{run.protocolHash && <CopyButton text={run.protocolHash} label="Copiar hash"/>}</div></section>
    <section className="surface events-section"><div className="section-heading"><div><h2>Histórico de eventos</h2><p>Registros disponíveis no snapshot, do mais recente ao mais antigo.</p></div><span className="quiet-label">{events.length} eventos</span></div><div className="event-toolbar"><label className="search-field"><Icon name="search" size={16}/><span className="sr-only">Filtrar eventos</span><input placeholder="Buscar tipo de evento" value={query} onChange={e => { setQuery(e.target.value); setLimit(30); }}/></label><label className="checkbox-label"><input type="checkbox" checked={errorsOnly} onChange={e => { setErrorsOnly(e.target.checked); setLimit(30); }}/>Somente falhas e rejeições</label></div>
      <div className="event-list">{events.slice(0, limit).map((e, i) => <details className="event" key={`${e.at}:${e.type}:${i}`}><summary><span className={/failed|error|timeout|rejected/.test(e.type) ? "event-dot error-dot" : "event-dot"}/><span className="event-name">{e.type}</span><time>{e.at ? new Date(e.at).toLocaleTimeString("pt-BR") : "Sem horário"}</time><Icon name="chevron" size={14}/></summary><pre>{JSON.stringify(e.payload, null, 2)}</pre></details>)}</div>
      {!events.length && <p className="empty-inline">{query || errorsOnly ? "Nenhum evento corresponde a este filtro." : "Esta leitura não inclui eventos."}</p>}{events.length > limit && <div className="load-more"><button className="button" onClick={() => setLimit(n => n + 30)}>Mostrar mais 30 eventos</button></div>}
    </section>
    <div className="raw-grid">{([["Configuração da tarefa", run.task], ["Jogadores", run.players], ["Orçamento declarado", run.budget], ["Consumo reportado", run.provider]] as const).map(([title, data]) => <details className="technical-details" key={title}><summary>{title}</summary><pre>{JSON.stringify(data ?? {}, null, 2)}</pre></details>)}</div>
  </div>;
}
