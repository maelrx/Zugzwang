import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chessground } from "chessground";
import type { Api } from "chessground/api";
import type { Color, Key } from "chessground/types";
import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";
import { Icon } from "./Icon";

interface ProviderModel { id: string; label: string; validated: boolean; default: boolean }
interface ProviderOption {
  id: string; backend_id: string; label: string; validated: boolean;
  models: ProviderModel[]; efforts: string[]; default_effort: string | null; note: string;
}
interface MoveRecord {
  ply: number; side: string; actor: string; uci: string; san: string;
  latency_ms?: number | null; tokens_out?: number | null; rounds?: number | null; error?: string | null;
}
interface ArenaGameState {
  id: string; created_at: string; setup: Record<string, unknown>;
  status: "human_turn" | "model_thinking" | "finished";
  human_color: "white" | "black"; model_color: "white" | "black";
  fen: string; turn: "white" | "black"; last_uci: string | null; check: boolean;
  moves: MoveRecord[]; thinking: boolean; last_error: string | null;
  result: { score: string; kind: string; winner: string | null } | null;
  dests: Record<string, string[]> | null; promotable: string[] | null;
}
interface GameSummary { id: string; created_at: string; status: string; human_color: string; plies: number; result: { score: string; kind: string } | null; setup: Record<string, unknown> }

const API = "/play/api";
const POLL_MS = 2000;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init ? { headers: { "Content-Type": "application/json" }, ...init } : undefined);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(String((body as { detail?: string }).detail ?? "falha na requisição")), { code: (body as { error?: string }).error });
  return body as T;
}

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
  const [games, setGames] = useState<GameSummary[]>([]);
  const [game, setGame] = useState<ArenaGameState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const cgRef = useRef<Api | null>(null);
  const gameRef = useRef<ArenaGameState | null>(null);
  useEffect(() => { gameRef.current = game; }, [game]);

  const [form, setForm] = useState({
    provider: "antigravity-cli", model: "gemini-3.8-flash-low", effort: "low",
    human_color: "white" as "white" | "black", max_rounds: 6, ascii: false, history_plies: 12, directive: "",
  });

  const refreshGames = useCallback(() => { void api<{ games: GameSummary[] }>("/games").then(b => setGames(b.games)).catch(() => undefined); }, []);
  const pollOnce = useCallback((id: string) => {
    void api<ArenaGameState>(`/games/${id}`).then(next => { setGame(next); if (!next.thinking) refreshGames(); }).catch(() => undefined);
  }, [refreshGames]);

  useEffect(() => {
    void api<{ providers: ProviderOption[] }>("/providers").then(b => {
      setProviders(b.providers);
      const first = b.providers.find(p => p.validated) ?? b.providers[0];
      if (!first) return;
      const model = first.models.find(m => m.default) ?? first.models[0];
      setForm(f => ({ ...f, provider: first.id, model: model?.id ?? "", effort: first.default_effort ?? "" }));
    }).catch(e => setError(`Serviço da arena indisponível (inicie com: uv run python -m zugzwang_cli.arena.server): ${e.message}`));
    refreshGames();
  }, [refreshGames]);

  // Poll while the model is thinking; stops on human turn / end of game.
  useEffect(() => {
    if (!game || game.status === "finished" || !game.thinking) return;
    const timer = window.setTimeout(() => pollOnce(game.id), POLL_MS);
    return () => window.clearTimeout(timer);
  }, [game, pollOnce]);

  const orientation: Color = (game ? game.human_color : form.human_color) as Color;

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
    setBusy(true); setError(null);
    try { setGame(await api<ArenaGameState>(`/games/${current.id}/moves`, { method: "POST", body: JSON.stringify({ uci }) })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, []);

  const onBoardMove = useCallback((from: Key, to: Key) => {
    const current = gameRef.current;
    if (!current || busy || current.thinking) return;
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
      movable: game.status === "human_turn" && !busy
        ? { free: false, color: orientation, showDests: true, dests, events: { after: (from: Key, to: Key) => onBoardMove(from, to) } }
        : { free: false, color: undefined, showDests: false, dests: new Map() },
      selectable: { enabled: false },
    });
  }, [game, orientation, busy, onBoardMove]);

  const createGame = useCallback(async () => {
    setBusy(true); setError(null); setPromotion(null);
    try {
      const created = await api<ArenaGameState>("/games", { method: "POST", body: JSON.stringify({ ...form, directive: form.directive || undefined }) });
      setGame(created);
      refreshGames();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, [form, refreshGames]);

  const act = useCallback(async (action: "retry" | "resign") => {
    const current = gameRef.current;
    if (!current) return;
    setBusy(true); setError(null);
    try { setGame(await api<ArenaGameState>(`/games/${current.id}/${action}`, { method: "POST", body: "{}" })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, []);

  const selectedProvider = useMemo(() => providers.find(p => p.id === form.provider), [providers, form.provider]);
  const pairs = useMemo(() => {
    if (!game) return [] as { number: number; white?: MoveRecord; black?: MoveRecord }[];
    const rows: { number: number; white?: MoveRecord; black?: MoveRecord }[] = [];
    for (const move of game.moves) {
      const number = Math.floor((move.ply - 1) / 2) + 1;
      const row = rows[number - 1] ?? (rows[number - 1] = { number });
      if (move.side === "white") row.white = move; else row.black = move;
    }
    return rows;
  }, [game]);
  const lastModel = useMemo(() => [...game?.moves ?? []].reverse().find(m => m.actor === "model"), [game]);
  const modelName = String(game?.setup.model ?? "Modelo");

  if (providers.length === 0 && !error) return <div className="loading-state" role="status"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-row" /></div>;

  return <div className="game-layout">
    <section className="board-section surface" aria-label="Tabuleiro da arena">
      <div className="player-strip"><span className={`piece-dot ${orientation === "white" ? "black" : "white"}`} /><div><span>{orientation === "white" ? "Pretas" : "Brancas"}</span><strong>{orientation === "white" ? modelName : "Você"}</strong></div><span className="quiet-label">{game?.thinking ? "pensando…" : ""}</span></div>
      <div className="board-wrap" style={{ position: "relative" }}>
        <div ref={boardRef} className="aspect-square w-full" style={{ borderRadius: 8, overflow: "hidden" }} role="img" aria-label="Tabuleiro interativo" />
        {promotion && <div role="dialog" aria-label="Escolher peça da promoção" style={{ position: "absolute", inset: 0, display: "flex", gap: 8, alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.45)", zIndex: 10 }}>
          {[["q", "Dama"], ["r", "Torre"], ["b", "Bispo"], ["n", "Cavalo"]].map(([piece, label]) => <button key={piece} className="button" onClick={() => { const move = promotion; setPromotion(null); void sendMove(`${move.from}${move.to}${piece}`); }}>{label}</button>)}
        </div>}
      </div>
      <div className="player-strip bottom"><span className={`piece-dot ${orientation === "white" ? "white" : "black"}`} /><div><span>{orientation === "white" ? "Brancas" : "Pretas"}</span><strong>{orientation === "white" ? "Você" : modelName}</strong></div><span className="quiet-label">{game ? `${game.moves.length} meios-lances` : "—"}</span></div>
      <div className="board-tools">
        <button className="button compact" disabled={!game || game.status === "finished" || busy} onClick={() => void act("resign")}>Desistir</button>
        <button className="button compact" disabled={!game || !game.thinking} onClick={() => game && pollOnce(game.id)}>Atualizar agora</button>
        <button className="button compact" disabled={!game || busy || game.status === "finished"} onClick={() => void act("retry")}>Repetir turno do modelo</button>
      </div>
      {error && <div className="notice error" role="alert"><Icon name="alert" /><div><strong>Não foi possível completar a ação</strong><p>{error}</p></div></div>}
      {game?.last_error && game.status !== "finished" && <div className="notice" role="status"><Icon name="alert" /><div><strong>Turno do modelo falhou</strong><p>{game.last_error}</p><p className="quiet-label">Seu lance permanece válido — use “Repetir turno do modelo”.</p></div></div>}
      {game?.result && <div className="notice" role="status"><div><strong>Partida encerrada: {game.result.score} ({game.result.kind})</strong><p>Use “Nova partida” na configuração para jogar de novo.</p></div></div>}
    </section>
    <div className="game-right">
      <section className="surface" aria-label="Configuração da partida">
        <div className="section-heading"><div><h2>Configuração</h2><p>Todo o setup da partida via UI — cada chamada ao modelo é registrada em <code>out/arena/</code>.</p></div></div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <label>Provedor<select value={form.provider} onChange={e => {
            const provider = providers.find(p => p.id === e.target.value);
            const model = provider?.models.find(m => m.default) ?? provider?.models[0];
            setForm(f => ({ ...f, provider: e.target.value, model: model?.id ?? "", effort: provider?.default_effort ?? "" }));
          }}>{providers.map(p => <option key={p.id} value={p.id}>{p.label}{p.validated ? " ✓" : ""}</option>)}</select></label>
          <label>Modelo<select value={form.model} onChange={e => setForm(f => ({ ...f, model: e.target.value }))}>{(selectedProvider?.models ?? []).map(m => <option key={m.id} value={m.id}>{m.label}{m.validated ? " ✓ validado" : ""}</option>)}</select></label>
          {(selectedProvider?.efforts.length ?? 0) > 0 && <label>Esforço<select value={form.effort} onChange={e => setForm(f => ({ ...f, effort: e.target.value }))}>{selectedProvider!.efforts.map(effort => <option key={effort} value={effort}>{effort}</option>)}</select></label>}
          <label>Sua cor<select value={form.human_color} onChange={e => setForm(f => ({ ...f, human_color: e.target.value as "white" | "black" }))}><option value="white">Brancas</option><option value="black">Pretas</option></select></label>
          <label>Rounds por lance<select value={form.max_rounds} onChange={e => setForm(f => ({ ...f, max_rounds: Number(e.target.value) }))}>{[2, 4, 6, 8].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
          <label>Histórico (plies)<select value={form.history_plies} onChange={e => setForm(f => ({ ...f, history_plies: Number(e.target.value) }))}>{[0, 6, 12, 24].map(n => <option key={n} value={n}>{n === 0 ? "sem histórico" : `últimos ${n}`}</option>)}</select></label>
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}><input type="checkbox" checked={form.ascii} onChange={e => setForm(f => ({ ...f, ascii: e.target.checked }))} />Incluir tabuleiro ASCII no pacote L0</label>
        <label style={{ display: "block", marginTop: 10 }}>Diretiva ao modelo (opcional)<textarea style={{ width: "100%" }} rows={3} value={form.directive} placeholder="Vazia = diretiva tática dos full games vencedores" onChange={e => setForm(f => ({ ...f, directive: e.target.value }))} /></label>
        <div className="board-tools" style={{ marginTop: 10 }}>
          <button className="button primary" disabled={busy} onClick={() => void createGame()}>{game ? "Nova partida" : "Iniciar partida"}</button>
          {game && <span className="mono quiet-label">{game.id}</span>}
        </div>
        {selectedProvider?.note && <p className="helper-text">{selectedProvider.note}</p>}
      </section>
      <section className="moves-section surface" aria-label="Lances da partida">
        <div className="section-heading"><div><h2>Lances</h2><p>{lastModel ? `Último lance do modelo: ${lastModel.san}` : "Faça seu lance no tabuleiro."}</p></div></div>
        <div className="moves-header"><span>#</span><span>Brancas</span><span>Pretas</span></div>
        <div className="move-list">
          {pairs.map(row => <div className="move-pair" key={row.number}><span className="move-number">{row.number}.</span>{(["white", "black"] as const).map(side => {
            const move = side === "white" ? row.white : row.black;
            return move ? <button key={side} title={move.actor === "model" && move.latency_ms ? `${(move.latency_ms / 1000).toFixed(1)}s · ${move.rounds ?? "?"} chamada(s)${move.tokens_out ? ` · ${move.tokens_out} tokens` : ""}` : "Seu lance"}><strong>{move.san}</strong>{move.actor === "model" && move.latency_ms != null && <span>{(move.latency_ms / 1000).toFixed(1)}s</span>}</button> : <span key={side} className="missing-move">—</span>;
          })}</div>)}
          {(!game || game.moves.length === 0) && <p className="empty-inline">Aguardando o primeiro lance.</p>}
        </div>
      </section>
      {games.length > 0 && <section className="surface" aria-label="Jogos anteriores">
        <div className="section-heading"><div><h2>Jogos anteriores</h2><p>Evidência bruta por chamada em <code>out/arena/</code> (JSONL + PGN).</p></div></div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {games.slice(0, 8).map(summary => <button key={summary.id} className="button compact" aria-pressed={game?.id === summary.id} onClick={() => pollOnce(summary.id)}>
            <strong>{String(summary.setup.model ?? summary.id)}</strong><span className="quiet-label"> {summary.plies} plies · {summary.status === "finished" ? `fim (${summary.result?.score ?? "?"})` : summary.status === "model_thinking" ? "pensando" : "em andamento"}</span>
          </button>)}
        </div>
      </section>}
    </div>
  </div>;
}
