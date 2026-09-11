import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chessground } from "chessground";
import type { Api } from "chessground/api";
import type { Color, Key } from "chessground/types";
import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";
import { Icon } from "./Icon";
import { ThinkingPanel } from "./ThinkingPanel";
import { PlayerBar, MoveBook, PromotionPicker } from "./ChessDesk";
import { modelName as displayModel, providerName, modelDetail } from "@/lib/arena";

import { api } from "@/lib/arena";
import type { ArenaGameState, ProviderOption } from "@/lib/arena";
const POLL_MS = 2000;

/** Piece letter at one square from a FEN placement, or null. */
function pieceAt(fen: string, square: string): string | null {
  const file = square.charCodeAt(0) - 97;
  const rank = 8 - Number(square[1]);
  let index = 0;
  for (const row of fen.split(" ")[0].split("/")) {
    for (const char of row) {
      if (/\d/.test(char)) { index += Number(char); continue; }
      if (Math.floor(index / 8) === rank && index % 8 === file) return char;
      index += 1;
    }
  }
  return null;
}

export function PlayView() {
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [setupOpen, setSetupOpen] = useState(true);
  const [flipped, setFlipped] = useState(false);
  const [resignConfirm, setResignConfirm] = useState(false);
  const [game, setGame] = useState<ArenaGameState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const cgRef = useRef<Api | null>(null);
  const gameRef = useRef<ArenaGameState | null>(null);
  const requestRef = useRef(0);
  const acceptGame = useCallback((next: ArenaGameState) => {
    setSetupOpen(false);
    setResignConfirm(false);
    gameRef.current = next;
    setGame(next);
    sessionStorage.setItem("arena-game", next.id);
  }, []);

  const [form, setForm] = useState({
    provider: "antigravity-cli", model: "gemini-3.8-flash-low", effort: "low", service_tier: "",
    human_color: "white" as "white" | "black", opponent: "human" as "human" | "stockfish",
    max_rounds: 6, ascii: false, history_plies: 12, directive: "",
  });

  const pollOnce = useCallback(async (id: string) => {
    const request = ++requestRef.current;
    try {
      const next = await api<ArenaGameState>(`/games/${id}`);
      if (request !== requestRef.current) return;
      acceptGame(next);
      setPromotion(null);
      setError(null);

    } catch {
      if (request === requestRef.current) setError("Conexão interrompida. Tente atualizar a partida; seu progresso fica salvo.");
    }
  }, [acceptGame]);

  useEffect(() => {
    void api<{ providers: ProviderOption[] }>("/providers").then(b => {
      setProviders(b.providers);
      const first = b.providers.find(p => p.id === "codex-cli" && p.available !== false) ?? b.providers.find(p => p.available !== false);
      if (!first) return;
      const model = first.models.find(m => m.default) ?? first.models[0];
      setForm(f => ({ ...f, provider: first.id, model: model?.id ?? "", effort: first.default_effort ?? "" }));
    }).catch(e => setError(`Não foi possível conectar à arena. Tente recarregar a página. ${e.message}`));
    const saved = sessionStorage.getItem("arena-game");
    if (saved) queueMicrotask(() => { void pollOnce(saved); });
  }, [pollOnce]);

  // Poll while the model is thinking; stops on human turn / end of game.
  useEffect(() => {
    if (!game || game.status === "finished" || !game.thinking) return;
    let stopped = false;
    let timer: number;
    const poll = async () => {
      await pollOnce(game.id);
      if (!stopped) timer = window.setTimeout(() => { void poll(); }, POLL_MS);
    };
    timer = window.setTimeout(() => { void poll(); }, POLL_MS);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [game, pollOnce]);

  const humanColor = game?.human_color ?? form.human_color;
  const orientation: Color = flipped ? (humanColor === "white" ? "black" : "white") : humanColor;

  // Interactive board lifecycle (create once; reconfigure on state change).
  useEffect(() => {
    if (!boardRef.current) return;
    cgRef.current = Chessground(boardRef.current, {
      viewOnly: false,
      animation: { enabled: !window.matchMedia("(prefers-reduced-motion: reduce)").matches, duration: 180 },
      drawable: { enabled: false, visible: false },
      coordinates: true,
    });
    return () => { cgRef.current?.destroy(); cgRef.current = null; };
  }, []);

  const sendMove = useCallback(async (uci: string) => {
    const current = gameRef.current;
    if (!current) return;
    ++requestRef.current;
    setBusy(true); setError(null);
    try { acceptGame(await api<ArenaGameState>(`/games/${current.id}/moves`, { method: "POST", body: JSON.stringify({ uci }) })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, [acceptGame]);

  const onBoardMove = useCallback((from: Key, to: Key) => {
    const current = gameRef.current;
    if (!current || busy || current.thinking || current.turn !== current.human_color) return;
    const piece = pieceAt(current.fen, from);
    if (current.promotable?.includes(to) && (piece === "P" || piece === "p")) { setPromotion({ from, to }); return; }
    void sendMove(`${from}${to}`);
  }, [busy, sendMove]);

  useEffect(() => {
    const cg = cgRef.current;
    if (!cg) return;
    if (!game) {
      cg.set({ fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR", orientation, movable: { free: false, color: undefined, showDests: false, dests: new Map() } });
      return;
    }
    const turnColor: Color = game.turn === "black" ? "black" : "white";
    const dests = new Map<Key, Key[]>(Object.entries(game.dests ?? {}).map(([k, v]) => [k as Key, v as Key[]]));
    cg.set({
      fen: game.fen.split(" ")[0],
      orientation,
      turnColor,
      lastMove: game.last_uci ? [game.last_uci.slice(0, 2) as Key, game.last_uci.slice(2, 4) as Key] : undefined,
      highlight: { lastMove: true, check: true },
      check: game.check ? turnColor : undefined,
      movable: game.status === "human_turn" && game.turn === game.human_color && !busy && !promotion
        ? { free: false, color: orientation, showDests: true, dests, events: { after: (from: Key, to: Key) => onBoardMove(from, to) } }
        : { free: false, color: undefined, showDests: false, dests: new Map() },
      selectable: { enabled: true },
    });
  }, [game, orientation, busy, promotion, onBoardMove]);

  const createGame = useCallback(async () => {
    ++requestRef.current;
    setBusy(true); setError(null); setPromotion(null);
    try {
      const created = await api<ArenaGameState>("/games", { method: "POST", body: JSON.stringify({ ...form, service_tier: form.provider === "codex-cli" && form.model === "gpt-5.6-luna" ? form.service_tier || undefined : undefined, directive: form.directive || undefined }) });
      setFlipped(false);
      acceptGame(created);
      } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, [form, acceptGame]);

  const act = useCallback(async (action: "retry" | "resign") => {
    const current = gameRef.current;
    if (!current) return;
    ++requestRef.current;
    setBusy(true); setError(null);
    try { acceptGame(await api<ArenaGameState>(`/games/${current.id}/${action}`, { method: "POST", body: "{}" })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, [acceptGame]);

  const selectedProvider = useMemo(() => providers.find(p => p.id === form.provider), [providers, form.provider]);
  const supportsFast = selectedProvider?.models.find(m => m.id === form.model)?.service_tiers?.includes("fast") ?? false;
  const engineThinking = game?.status === "engine_thinking";
  const spectator = (game?.opponent ?? form.opponent) === "stockfish";
  const engineColor = game?.human_color ?? form.human_color;
  const sideName = (color: string) => spectator ? (color === engineColor ? "Stockfish 1320" : currentModelLabel) : (color === humanColor ? "Você" : currentModelLabel);
  const sideProvider = (color: string) => spectator && color === engineColor ? "stockfish" : currentProvider;
  const sideHuman = (color: string) => !spectator && color === humanColor;
  const sideThinking = (color: string) => !!game?.thinking && ((color === engineColor) === engineThinking);
  const canRetry = game && game.status !== "finished" && !game.thinking && game.turn !== game.human_color && !spectator;
  const currentModel = game?.setup.model ?? form.model;
  const currentProvider = game?.setup.provider ?? form.provider;
  const currentTier = game ? game.setup.service_tier : form.service_tier;
  const currentModelLabel = `${displayModel(currentModel)}${currentTier === "fast" ? " · Fast" : ""}`;
  const topColor = orientation === "white" ? "black" : "white";
  const isFinished = game?.status === "finished";
  const statusText = isFinished ? "Partida encerrada" : engineThinking ? "Stockfish está pensando" : game?.thinking ? "O modelo está pensando" : spectator ? "Partida em andamento" : canRetry ? "O modelo não concluiu o lance" : game?.check ? "Você está em xeque" : "Sua vez de jogar";
  const resultText = game?.result ? game.result.score === "1/2-1/2" ? "Empate" : game.result.score === (game.human_color === "white" ? "1-0" : "0-1") ? "Você venceu" : "O modelo venceu" : "";
  const setProvider = (id:string) => {
    const provider = providers.find(p => p.id === id);
    if (provider?.available === false) return;
    const model = provider?.models.find(m => m.default) ?? provider?.models[0];
    setForm(f => ({...f,provider:id,service_tier:"",model:model?.id ?? "",effort:provider?.default_effort ?? ""}));
  };

  return <div className="chess-desk play-desk">
    <header className="desk-heading"><div><h1>Jogar</h1><span>Você contra os modelos</span></div><a className="desk-text-link" href="#historico"><Icon name="clock" size={15}/>Suas partidas<Icon name="chevron" size={13}/></a></header>
    <div className="desk-layout">
      <section className="desk-board-column" aria-label="Tabuleiro da arena">
        <PlayerBar name={sideName(topColor)} provider={sideProvider(topColor)} human={sideHuman(topColor)} color={topColor} active={!!game && !isFinished && game.turn === topColor} status={sideThinking(topColor) ? "Pensando…" : undefined}/>
        <div className="desk-board-frame"><div ref={boardRef} className="desk-chessboard" aria-label="Tabuleiro interativo"/></div>
        <PlayerBar name={sideName(orientation)} provider={sideProvider(orientation)} human={sideHuman(orientation)} color={orientation} active={!!game && !isFinished && game.turn === orientation} status={spectator ? (sideThinking(orientation) ? "Pensando…" : undefined) : game && !isFinished && !game.thinking && game.turn === orientation ? "Sua vez" : undefined}/>
        <div className="desk-board-tools"><span>{!game ? "Escolha o oponente para começar." : isFinished ? "Partida salva no histórico." : spectator ? (engineThinking ? "O Stockfish está calculando o lance." : "Partida automática: o modelo joga contra o Stockfish 1320.") : game.thinking ? "Aguarde a resposta do modelo." : "Clique na peça e no destino, ou arraste."}</span><button className="desk-icon-button" aria-label="Virar tabuleiro" title="Virar tabuleiro" onClick={()=>setFlipped(f=>!f)}><Icon name="flip" size={17}/></button></div>
      </section>
      {setupOpen ? <aside className="desk-side desk-setup-side" aria-label="Configurar nova partida">
        <div className="desk-side-heading"><div><span className="desk-overline">NOVA PARTIDA</span><h2>Escolha seu oponente</h2></div>{game && <button className="desk-icon-button" aria-label="Voltar à partida atual" onClick={()=>setSetupOpen(false)}><Icon name="close" size={16}/></button>}</div>
        <form className="desk-setup" onSubmit={e=>{e.preventDefault();void createGame();}}>
          <fieldset className="desk-provider-picker"><legend>Provedor</legend>{providers.length ? providers.map(p=><label key={p.id} data-selected={form.provider === p.id} title={p.unavailable_reason}><input type="radio" name="provider" value={p.id} disabled={p.available === false} checked={form.provider===p.id} onChange={()=>setProvider(p.id)}/><span className="desk-provider-letter" aria-hidden="true">{providerName(p.id).slice(0,1)}</span><strong>{providerName(p.id)}{p.available === false ? " · indisponível" : ""}</strong>{form.provider===p.id && <Icon name="check" size={12}/>}</label>) : <div className="desk-loading-inline" role="status">Carregando modelos…</div>}</fieldset>
          <label className="desk-field">Modelo<select name="model" value={form.model} disabled={!providers.length} onChange={e=>setForm(f=>({...f,model:e.target.value,service_tier:""}))}>{(selectedProvider?.models ?? []).map(m=><option key={m.id} value={m.id}>{displayModel(m.id)}{modelDetail(m.id)!==m.id ? ` · ${modelDetail(m.id)}` : ""}</option>)}</select></label>
          {supportsFast && <fieldset className="desk-speed"><legend>Velocidade do Luna</legend><div>{[["", "Padrão"], ["fast", "Fast"]].map(([tier,label]) => <label key={tier} data-selected={form.service_tier === tier}><input type="radio" name="service-tier" value={tier} checked={form.service_tier === tier} onChange={()=>setForm(f=>({...f,service_tier:tier}))}/><span>{label}</span>{form.service_tier===tier && <Icon name="check" size={13}/>}</label>)}</div></fieldset>}
          <fieldset className="desk-color-picker"><legend>Oponente</legend>{(["human","stockfish"] as const).map(op=><label key={op} data-selected={form.opponent===op}><input type="radio" name="opponent" checked={form.opponent===op} onChange={()=>setForm(f=>({...f,opponent:op}))}/><span><strong>{op === "human" ? "Você mesmo" : "Stockfish 1320"}</strong><small>{op === "human" ? "Jogo interativo" : "Partida automática até mate ou empate"}</small></span>{form.opponent===op && <Icon name="check" size={13}/>}</label>)}</fieldset>
          <fieldset className="desk-color-picker"><legend>{form.opponent === "stockfish" ? "Stockfish joga de" : "Você joga de"}</legend>{(["white","black"] as const).map(color=><label key={color} data-selected={form.human_color===color}><input type="radio" name="human_color" checked={form.human_color===color} onChange={()=>setForm(f=>({...f,human_color:color}))}/><i className={`desk-side-piece ${color}`}/><span><strong>{color === "white" ? "Brancas" : "Pretas"}</strong><small>{color === "white" ? "Você começa" : "Modelo começa"}</small></span>{form.human_color===color && <Icon name="check" size={13}/>}</label>)}</fieldset>
          <details className="desk-advanced"><summary><Icon name="sliders" size={15}/>Ajustar setup<Icon name="chevron" size={13}/></summary><div>
            {!!selectedProvider?.efforts.length && <label className="desk-field">Esforço do modelo<select name="effort" value={form.effort} onChange={e=>setForm(f=>({...f,effort:e.target.value}))}>{selectedProvider.efforts.map(e=><option key={e} value={e}>{e}</option>)}</select></label>}
            <div className="desk-field-pair"><label className="desk-field">Chamadas por lance<select name="max_rounds" value={form.max_rounds} onChange={e=>setForm(f=>({...f,max_rounds:Number(e.target.value)}))}>{[2,4,6,8].map(n=><option key={n}>{n}</option>)}</select></label><label className="desk-field">Histórico enviado<select name="history_plies" value={form.history_plies} onChange={e=>setForm(f=>({...f,history_plies:Number(e.target.value)}))}>{[0,6,12,24].map(n=><option key={n} value={n}>{n ? `${n} meios-lances` : "Nenhum"}</option>)}</select></label></div>
            <label className="desk-check"><input type="checkbox" checked={form.ascii} onChange={e=>setForm(f=>({...f,ascii:e.target.checked}))}/>Enviar o tabuleiro também em texto</label>
            <label className="desk-field">Instrução adicional<textarea name="directive" autoComplete="off" rows={3} placeholder="Ex.: priorize a segurança do rei…" value={form.directive} onChange={e=>setForm(f=>({...f,directive:e.target.value}))}/></label>
          </div></details>
          {error && <div className="desk-error" role="alert"><Icon name="alert" size={15}/><p>{error}</p></div>}
          <div className="desk-start"><button className="desk-button primary" type="submit" disabled={busy || !providers.length || game?.thinking}><Icon name="play" size={16}/>{busy ? "Iniciando…" : form.opponent === "stockfish" ? "Assistir partida" : `Jogar de ${form.human_color === "white" ? "brancas" : "pretas"}`}</button><p><Icon name="check" size={13}/>{game ? "A partida atual continua no histórico." : "Seu progresso é salvo a cada lance."}</p></div>
        </form>
      </aside> : <aside className="desk-side desk-game-side" aria-label="Partida em andamento">
        <div className="desk-game-status" role="status"><span className={`desk-status-orb ${game?.thinking ? "thinking" : ""}`}><Icon name={isFinished ? "check" : canRetry ? "alert" : game?.thinking ? "clock" : "play"} size={19}/></span><div><h2>{busy ? "Salvando lance…" : statusText}</h2><p>{isFinished ? `${resultText} · ${game?.result?.score}` : game?.thinking ? `${currentModelLabel} está escolhendo o lance.` : canRetry ? "Seu último lance está salvo." : "Encontre sua melhor continuação."}</p></div></div>
        {error && <div className="desk-error" role="alert"><Icon name="alert" size={15}/><p>{error}</p></div>}
        <ThinkingPanel key={game?.model_progress?.turn_id ?? game?.id} progress={game?.model_progress} thinking={!!game?.thinking}/>
        {canRetry && <div className="desk-retry"><button className="desk-button" disabled={busy} onClick={()=>void act("retry")}><Icon name="refresh" size={15}/>Tentar turno novamente</button>{game?.last_error && <details><summary>Detalhes do erro</summary><p>{game.last_error}</p></details>}</div>}
        <div className="desk-book-title"><h3>Lances</h3><span>{game?.moves.length ?? 0} meios-lances</span></div>
        <MoveBook moves={game?.moves ?? []} positions={game?.positions} humanColor={humanColor} selected={game?.moves.length}/>
        <div className="desk-game-footer">
          {isFinished && <a className="desk-button primary" href={`#historico/${game?.id}`}><Icon name="chart" size={16}/>Rever partida e análise</a>}
          {resignConfirm ? <div className="desk-resign-confirm"><p>Encerrar esta partida?</p><button className="desk-button quiet" onClick={()=>setResignConfirm(false)}>Voltar</button><button className="desk-button danger" disabled={busy} onClick={()=>void act("resign")}>Confirmar desistência</button></div> : <div className="desk-game-actions"><button className="desk-button" disabled={busy || game?.thinking} onClick={()=>setSetupOpen(true)}><Icon name="play" size={14}/>Nova partida</button>{!isFinished && <button className="desk-button quiet" disabled={busy || game?.thinking} onClick={()=>setResignConfirm(true)}>Desistir</button>}</div>}
          <div className="desk-saved"><span><Icon name="check" size={12}/>Partida salva</span><button className="desk-icon-button" title="Atualizar partida" aria-label="Atualizar partida" disabled={busy} onClick={()=>game && void pollOnce(game.id)}><Icon name="refresh" size={14}/></button></div>
        </div>
      </aside>}
    </div>
    {promotion && <PromotionPicker onCancel={()=>setPromotion(null)} onSelect={piece=>{const move=promotion;setPromotion(null);void sendMove(`${move.from}${move.to}${piece}`);}}/>}
  </div>;
}
