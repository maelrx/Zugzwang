import { useMemo, useState } from "react";
import type { Run } from "@/lib/types";
import { activityAt, ageLabel, conditionLabel, experimentLabel, modelLabel, resultLabel, routeFor, runState, runTitle, shortId } from "@/lib/presentation";
import type { StatusFilter } from "@/lib/presentation";
import { fmtNum } from "@/lib/format";
import { Icon } from "./Icon";

export function RunsOverview({ runs, query, setQuery, status, setStatus, selected, onSelect, onCompare }: {
  runs: Run[]; query: string; setQuery: (s: string) => void; status: StatusFilter; setStatus: (s: StatusFilter) => void;
  selected: string[]; onSelect: (id: string) => void; onCompare: () => void;
}) {
  const [model, setModel] = useState("");
  const [experiment, setExperiment] = useState("");
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(0);
  const models = useMemo(() => [...new Set(runs.map(modelLabel))].sort(), [runs]);
  const experiments = useMemo(() => [...new Set(runs.map(r => r.experiment).filter(Boolean))].sort(), [runs]);
  const counts = useMemo(() => ({ all: runs.length, running: runs.filter(r => runState(r).key === "running").length,
    completed: runs.filter(r => runState(r).key === "completed").length, attention: runs.filter(r => runState(r).key === "attention").length }), [runs]);
  const filtered = useMemo(() => {
    const q = query.trim().toLocaleLowerCase();
    return runs.filter(r => (status === "all" || runState(r).key === status)
      && (!model || modelLabel(r) === model) && (!experiment || r.experiment === experiment)
      && (!q || [r.id, r.experiment, r.conditionId, modelLabel(r), conditionLabel(r), ...(r.tags ?? [])].join(" ").toLocaleLowerCase().includes(q)))
      .sort((a, b) => sort === "name" ? runTitle(a).localeCompare(runTitle(b)) : sort === "moves"
        ? b.episodes.reduce((s, e) => s + (e.moves?.length ?? 0), 0) - a.episodes.reduce((s, e) => s + (e.moves?.length ?? 0), 0)
        : (activityAt(b) ?? 0) - (activityAt(a) ?? 0));
  }, [runs, query, status, model, experiment, sort]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / 12));
  const safePage = Math.min(page, pageCount - 1);
  const visible = filtered.slice(safePage * 12, safePage * 12 + 12);
  const reset = () => { setQuery(""); setStatus("all"); setModel(""); setExperiment(""); setPage(0); };
  return <>
    <div className="page-heading"><div><p className="eyebrow">Biblioteca de pesquisa</p><h1>Partidas</h1><p className="lead">Encontre uma execução e acompanhe cada decisão.</p></div><span className="quiet-label">{runs.length} execuções registradas</span></div>
    <div className="status-tabs" aria-label="Filtrar por estado">
      {([["all", "Todas"], ["running", "Em execução"], ["completed", "Concluídas"], ["attention", "Precisam de atenção"]] as const).map(([id, label]) =>
        <button key={id} aria-pressed={status === id} onClick={() => { setStatus(id); setPage(0); }} className={status === id ? "active" : ""}>{label}<span>{counts[id]}</span></button>)}
    </div>
    <section className="library" aria-label="Biblioteca de execuções">
      <div className="filter-toolbar">
        <label className="search-field"><Icon name="search"/><span className="sr-only">Buscar execução</span><input type="search" value={query} placeholder="Buscar por nome, modelo ou ID" onChange={e => { setQuery(e.target.value); setPage(0); }}/></label>
        <label className="filter-select"><span>Modelo</span><select aria-label="Filtrar por modelo" value={model} onChange={e => { setModel(e.target.value); setPage(0); }}><option value="">Todos os modelos</option>{models.map(m => <option key={m}>{m}</option>)}</select></label>
        <label className="filter-select"><span>Experimento</span><select aria-label="Filtrar por experimento" value={experiment} onChange={e => { setExperiment(e.target.value); setPage(0); }}><option value="">Todos os experimentos</option>{experiments.map(e => <option value={e} key={e}>{experimentLabel(e)}</option>)}</select></label>
      </div>
      <div className="table-toolbar"><span>{filtered.length} {filtered.length === 1 ? "execução encontrada" : "execuções encontradas"}</span><label>Ordenar <select aria-label="Ordenar execuções" value={sort} onChange={e => { setSort(e.target.value); setPage(0); }}><option value="recent">Atividade recente</option><option value="name">Nome</option><option value="moves">Mais lances</option></select></label></div>
      <div className="table-scroll"><table className="runs-table"><thead><tr><th className="select-column"><span className="sr-only">Selecionar para comparação</span></th><th>Execução / modelo</th><th>Estado / resultado</th><th className="numeric">Lances</th><th className="numeric secondary-column">Chamadas</th><th className="activity-column">Última atividade</th><th><span className="sr-only">Abrir</span></th></tr></thead><tbody>
        {visible.map(r => { const st = runState(r); const plies = r.episodes.reduce((s, e) => s + (e.moves?.length ?? 0), 0); const last = activityAt(r); return <tr key={r.id} className={selected.includes(r.id) ? "row-selected" : ""}>
          <td className="select-column"><input type="checkbox" aria-label={`Comparar ${shortId(r.id)}`} checked={selected.includes(r.id)} disabled={selected.length >= 3 && !selected.includes(r.id)} onChange={() => onSelect(r.id)}/></td>
          <td className="identity-cell"><a className="run-link" href={routeFor(r.id)} title={r.experiment}>{runTitle(r)}</a><span className="model-name">{modelLabel(r)}</span><span className="run-condition" title={conditionLabel(r)}>{conditionLabel(r)}</span></td>
          <td className="state-cell"><span className={`state-badge tone-${st.tone}`} title={st.detail}><i/>{st.label}</span><span className="result-label">{r.episodes.length > 1 ? `${r.episodes.length} episódios` : resultLabel(r.episodes[0])}</span></td>
          <td className="numeric">{plies}<span className="cell-secondary">meios-lances</span></td><td className="numeric secondary-column">{typeof r.provider?.calls === "number" ? fmtNum(r.provider.calls) : "—"}<span className="cell-secondary">{r.provider?.failures ? `${r.provider.failures} falhas` : "concluídas"}</span></td>
          <td className="activity-column"><span title={last ? new Date(last).toLocaleString("pt-BR") : undefined}>{ageLabel(last)}</span><span className="cell-secondary mono">{shortId(r.id)}</span></td><td><a className="icon-button" href={routeFor(r.id)} aria-label={`Abrir execução ${shortId(r.id)}`}><Icon name="chevron" size={16}/></a></td>
        </tr>; })}
      </tbody></table></div>
      {!filtered.length && <div className="empty-state"><Icon name="search" size={28}/><h2>{runs.length ? "Nenhuma execução corresponde aos filtros" : "Sua biblioteca começa com a primeira execução"}</h2><p>{runs.length ? "Tente outro nome ou remova os filtros para ver todas as partidas." : "As execuções aparecerão aqui quando os dados do workspace estiverem disponíveis."}</p>{runs.length > 0 && <button className="button" onClick={reset}>Limpar filtros</button>}</div>}
      <footer className="table-footer"><span>{filtered.length ? `${safePage * 12 + 1}–${Math.min((safePage + 1) * 12, filtered.length)} de ${filtered.length}` : "0 resultados"}</span><span className="compare-hint">Selecione até 3 execuções para comparar</span><div className="pagination"><button className="icon-button" disabled={safePage === 0} aria-label="Página anterior" onClick={() => setPage(safePage - 1)}><Icon name="back" size={16}/></button><span>{safePage + 1} / {pageCount}</span><button className="icon-button" disabled={safePage + 1 >= pageCount} aria-label="Próxima página" onClick={() => setPage(safePage + 1)}><Icon name="arrow" size={16}/></button></div></footer>
    </section>
    {selected.length > 0 && <div className="comparison-dock" role="region" aria-label="Seleção de comparação"><Icon name="compare"/><span>{selected.length} {selected.length === 1 ? "execução selecionada" : "execuções selecionadas"}</span><div className="dock-selection">{selected.map(id => <button key={id} className="selected-chip" onClick={() => onSelect(id)} aria-label={`Remover ${shortId(id)} da comparação`}>{shortId(id)}<Icon name="close" size={12}/></button>)}</div><button className="button primary" disabled={selected.length < 2} onClick={onCompare}>Comparar execuções <Icon name="arrow" size={16}/></button></div>}
  </>;
}
