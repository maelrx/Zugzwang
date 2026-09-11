import { useEffect, useRef, useState } from "react";
import type { ModelProgress } from "@/lib/arena";
import { Icon } from "./Icon";

const phaseLabel = (phase: string) => ({preparing:"Preparando a posição",waiting:"Aguardando resposta",received:"Resposta recebida",tool:"Consultando o tabuleiro",selected:"Lance escolhido",completed:"Lance concluído",failed:"Turno interrompido"}[phase] ?? "Acompanhando o turno");
const toolLabel = (tool: string | null) => ({board_observe:"Posição consultada",board_inspect:"Fatos da posição verificados",board_expand:"Variantes exploradas",board_compare:"Posições comparadas"}[tool ?? ""] ?? "Ferramenta consultada");

export function ThinkingPanel({progress, thinking}: {progress?: ModelProgress | null; thinking: boolean}) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  const listRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);
  useEffect(() => {
    if (!thinking) return;
    const timer = window.setInterval(() => setNow(Date.now()/1000), 1000);
    return () => window.clearInterval(timer);
  }, [thinking]);
  useEffect(() => {
    const list = listRef.current;
    if (list && followRef.current) list.scrollTop = list.scrollHeight;
  }, [progress?.summaries]);
  if (!progress) return thinking ? <div className="desk-thinking-empty">Aguardando informações deste turno…</div> : null;
  const elapsed = Math.max(0, Math.floor((progress.finished_at ?? now) - progress.started_at));
  const duration = elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed/60)}m ${elapsed%60}s`;
  const lastStep = [...progress.steps].reverse().find(step => step.kind === "tool");
  const phase = progress.status === "interrupted" ? "Turno interrompido" : phaseLabel(progress.phase);
  return <details className="desk-thinking" open={thinking}>
    <summary>
      <span className={`desk-thinking-symbol ${thinking ? "is-active" : ""}`}><Icon name={thinking ? "clock" : progress.status === "completed" ? "check" : "alert"} size={14}/></span>
      <span>{thinking ? "Pensamento do modelo" : "Resumo do último turno"}</span>
      <span className="desk-thinking-duration">{duration}</span>
      <span className="desk-thinking-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="desk-thinking-content">
      <div className="desk-thinking-meta"><span role="status" aria-live="polite">{phase}</span><span>Rodada {progress.round || "—"}<small> / {progress.max_rounds}</small></span></div>
      <div className="desk-thinking-scroll" ref={listRef} tabIndex={0} aria-label="Resumos do pensamento do modelo" onScroll={e => {const el=e.currentTarget;followRef.current=el.scrollHeight-el.scrollTop-el.clientHeight<28;}}>
        {progress.summaries.length ? progress.summaries.map(summary => <article className="desk-thought" key={summary.id}><div><span>Rodada {summary.round}</span><span>Resumo do provedor</span></div><p>{summary.text}</p></article>) : <p className="desk-thinking-empty">{thinking ? progress.streaming ? "O resumo aparece aqui assim que o modelo o enviar." : "Este provedor não transmite resumos ao vivo. Você pode acompanhar as etapas do turno." : "O provedor não disponibilizou um resumo neste turno."}</p>}
      </div>
      {lastStep && <div className="desk-thinking-step"><Icon name={lastStep.ok ? "check" : "alert"} size={12}/><span>{lastStep.ok ? toolLabel(lastStep.tool) : "Consulta recusada; o modelo recebeu o aviso."}</span></div>}
    </div>
  </details>;
}
