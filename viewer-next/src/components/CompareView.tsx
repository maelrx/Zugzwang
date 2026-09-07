import type { Run } from "@/lib/types";
import { comparable, conditionLabel, modelLabel, resultLabel, routeFor, runState, runTitle, shortId } from "@/lib/presentation";
import { fmtNum } from "@/lib/format";
import { Icon } from "./Icon";
export function CompareView({ runs, onBack }: { runs: Run[]; onBack: () => void }) {
  const same = comparable(runs);
  const rows: [string, (r: Run) => string][] = [
    ["Modelo", modelLabel], ["Condição", conditionLabel], ["Estado", r => runState(r).label],
    ["Resultado", r => r.episodes.length === 1 ? resultLabel(r.episodes[0]) : `${r.episodes.length} episódios`],
    ["Meios-lances registrados", r => String(r.episodes.reduce((n, e) => n + (e.moves?.length ?? 0), 0))],
    ["Chamadas concluídas", r => r.provider?.calls == null ? "—" : String(r.provider.calls)],
    ["Falhas de chamada", r => r.provider?.failures == null ? "—" : String(r.provider.failures)],
    ["Tokens de entrada", r => r.provider?.tokens?.input == null ? "—" : fmtNum(r.provider.tokens.input)],
    ["Tokens de saída", r => r.provider?.tokens?.output == null ? "—" : fmtNum(r.provider.tokens.output)],
    ["Assistência declarada", r => r.declaredAssistance ?? "Não informada"],
    ["Assistência efetiva", r => r.effectiveAssistance ?? "Não informada"],
    ["Hash do protocolo", r => r.protocolHash ?? "Não informado"],
  ];
  return <><div className="page-heading"><div><p className="eyebrow">Exploração lado a lado</p><h1>Comparar execuções</h1><p className="lead">O mesmo contexto visual para examinar diferenças.</p></div><button className="button" onClick={onBack}><Icon name="back"/>Voltar à biblioteca</button></div>
    {runs.length < 2 ? <div className="empty-state"><Icon name="compare" size={32}/><h2>Escolha duas ou três execuções</h2><p>Use as caixas de seleção na biblioteca para montar uma comparação.</p><button className="button primary" onClick={onBack}>Escolher execuções</button></div> : <>
      <div className="notice"><Icon name="alert"/><div><strong>{same ? "Mesmo hash de protocolo" : "Comparabilidade não confirmada"}</strong><p>{same ? "Confira também modelo, posições e orçamento antes de interpretar diferenças." : "Os protocolos diferem ou não foram informados. Esta comparação é descritiva e não estabelece um ranking."}</p></div></div>
      <div className="library table-scroll"><table className="compare-table"><thead><tr><th>Medida</th>{runs.map(r => <th key={r.id}><span className="quiet-label mono">{shortId(r.id)}</span><h2>{runTitle(r)}</h2><a href={routeFor(r.id)}>Explorar partida <Icon name="arrow" size={14}/></a></th>)}</tr></thead><tbody>{rows.map(([label, get]) => <tr key={label}><th>{label}</th>{runs.map(r => <td key={r.id}>{get(r)}</td>)}</tr>)}</tbody></table></div>
    </>}
  </>;
}
