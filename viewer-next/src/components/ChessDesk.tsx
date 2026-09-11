import { useEffect, useRef, useState } from "react";
import type { AnalysisPosition, MoveRecord, ReplayPosition } from "@/lib/arena";
import { moveLoss, providerName } from "@/lib/arena";
import { Icon } from "./Icon";
import "./ChessDesk.css";

export function ModelMark({ provider, human = false }: { provider?: unknown; human?: boolean }) {
  return <span className={`desk-avatar ${human ? "human" : ""}`} aria-hidden="true">{human ? <Icon name="user"/> : providerName(provider).slice(0,1)}</span>;
}
export function PlayerBar({name, provider, human, color, active, status}: { name: string; provider?: unknown; human: boolean; color: "white" | "black"; active?: boolean; status?: string }) {
  return <div className={`desk-player ${active ? "is-turn" : ""}`}><ModelMark provider={provider} human={human}/><div className="desk-player-name"><strong title={name}>{name}</strong><span><i className={`desk-color-dot ${color}`}/>{color === "white" ? "Brancas" : "Pretas"}</span></div>{status && <span className="desk-player-status">{active && <i/>}{status}</span>}</div>;
}
export function MoveBook({moves, positions, humanColor, selected, analysis, onSelect}: { moves: MoveRecord[]; positions?: ReplayPosition[]; humanColor: "white" | "black"; selected?: number; analysis?: AnalysisPosition[]; onSelect?: (ply:number)=>void }) {
  const ref = useRef<HTMLDivElement>(null);
  const pairs: { number:number; white?:MoveRecord; black?:MoveRecord }[] = [];
  for (const move of moves) {
    const number = positions?.[move.ply - 1]?.fullmove ?? Math.ceil(move.ply / 2);
    let pair = pairs.find(row => row.number === number);
    if (!pair) { pair = {number}; pairs.push(pair); }
    pair[move.side === "white" ? "white" : "black"] = move;
  }
  useEffect(() => {
    const list = ref.current;
    const current = list?.querySelector<HTMLElement>('[data-current="true"]');
    if (!list || !current) return;
    const top = current.offsetTop;
    if (top < list.scrollTop || top + current.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = Math.max(0, top - list.clientHeight / 2 + current.offsetHeight / 2);
    }
  }, [selected]);
  return <div className="desk-book"><div className="desk-book-head"><span>#</span><span><i className="desk-color-dot white"/>{humanColor === "white" ? "Você" : "Modelo"}</span><span><i className="desk-color-dot black"/>{humanColor === "black" ? "Você" : "Modelo"}</span></div><div className="desk-book-list" ref={ref}>
    {!moves.length ? <div className="desk-book-empty"><Icon name="grid" size={24}/><p>Os lances aparecem aqui.</p><span>{onSelect ? "Esta partida ainda não teve lances." : "Sua partida começa no tabuleiro."}</span></div> : pairs.map(pair => <div className="desk-book-row" key={pair.number}><span className="desk-move-number">{pair.number}.</span>{(["white","black"] as const).map(side => {
      const move = pair[side];
      if (!move) return <span className="desk-move-missing" key={side}>·</span>;
      const loss = moveLoss(analysis?.[move.ply - 1], analysis?.[move.ply], side);
      const contents = <><strong>{move.san}</strong>{loss != null && loss >= 50 && <small className={loss >= 200 ? "loss-large" : ""} title={`${loss} centipeões de perda`}>−{(loss / 100).toFixed(2)}</small>}</>;
      return onSelect ? <button key={side} data-current={selected === move.ply} aria-current={selected === move.ply ? "step" : undefined} aria-label={`${pair.number}${side === "white" ? "." : "…"} ${move.san}`} onClick={() => onSelect(move.ply)}>{contents}</button> : <div className="desk-live-move" key={side} data-current={selected === move.ply}>{contents}</div>;
    })}</div>)}
  </div></div>;
}
export function ClipboardButton({value, label="Copiar FEN"}: { value:string; label?:string }) {
  const [copied,setCopied] = useState(false);
  const [failed,setFailed] = useState(false);
  return <><button className="desk-button small" onBlur={() => {setCopied(false);setFailed(false);}} onClick={async () => {try {await navigator.clipboard.writeText(value);setCopied(true);} catch {setFailed(true);}}}><Icon name={copied ? "check" : "copy"} size={14}/>{copied ? "Copiado" : label}</button><span className="sr-only" role="status">{copied ? "FEN copiado" : failed ? "Selecione o texto para copiar manualmente." : ""}</span></>;
}
export function PromotionPicker({onSelect,onCancel}: {onSelect:(piece:string)=>void;onCancel:()=>void}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const el = ref.current; el?.showModal(); return () => el?.close(); }, []);
  return <dialog ref={ref} className="desk-promotion" onCancel={e=>{e.preventDefault();onCancel();}} aria-labelledby="promotion-heading"><h2 id="promotion-heading">Promover peão</h2><p>Escolha a peça para concluir o lance.</p><div>{[["q","Dama"],["r","Torre"],["b","Bispo"],["n","Cavalo"]].map(([piece,label])=><button className="desk-button" key={piece} onClick={()=>onSelect(piece)}>{label}</button>)}</div><button className="desk-button quiet" onClick={onCancel}>Voltar ao tabuleiro</button></dialog>;
}
