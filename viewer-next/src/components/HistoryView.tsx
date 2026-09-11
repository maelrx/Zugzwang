import { useEffect, useMemo, useState } from "react";
import { api, analysisLabel, moveLoss, scoreLabel, API, modelName, providerName } from "@/lib/arena";
import type { AnalysisPosition, AnalysisState, ArenaGameState, GameSummary } from "@/lib/arena";
import { Board } from "./Board";
import { Icon } from "./Icon";
import { ClipboardButton, ModelMark, MoveBook, PlayerBar } from "./ChessDesk";

const dayLabel = (value:string) => new Date(value).toLocaleDateString("pt-BR", {day:"2-digit",month:"short"});
const timeLabel = (value:string) => new Date(value).toLocaleTimeString("pt-BR", {hour:"2-digit",minute:"2-digit"});
const gameResult = (game: GameSummary | ArenaGameState) => !game.result ? "Em andamento" : game.result.score === "1/2-1/2" ? "Empate" : game.result.score === (game.human_color === "white" ? "1-0" : "0-1") ? "Você venceu" : "Modelo venceu";
const resultTone = (game: GameSummary | ArenaGameState) => !game.result ? "pending" : gameResult(game) === "Você venceu" ? "win" : "ended";
const resume = (id:string) => {sessionStorage.setItem("arena-game",id);window.location.hash="jogar";};
const cpValue = (row?:AnalysisPosition) => row?.cp_white ?? (row?.mate_white != null ? (row.mate_white > 0 || row.winner === "white" ? 1000 : -1000) : null);

function EvalGraph({rows,ply,total}: {rows:AnalysisPosition[];ply:number;total:number}) {
  const points = rows.flatMap(row => {const cp=cpValue(row);return cp == null ? [] : [`${12 + row.ply/Math.max(1,total)*376},${42-Math.max(-600,Math.min(600,cp))/600*30}`];});
  return <svg className="desk-eval-chart" viewBox="0 0 400 84" role="img" aria-label="Vantagem das brancas ao longo da partida; escala de menos seis a mais seis peões">
    <line x1="12" y1="42" x2="388" y2="42" className="desk-chart-zero"/>
    {points.length>1 && <polyline points={points.join(" ")} fill="none" stroke="var(--desk-accent)" strokeWidth="2"/>}
    <line x1={12+ply/Math.max(1,total)*376} y1="8" x2={12+ply/Math.max(1,total)*376} y2="76" className="desk-chart-position"/>
    <text x="12" y="10">+6</text><text x="12" y="82">−6</text>
  </svg>;
}

export function HistoryView({gameId}: {gameId:string}) {
  const [games,setGames]=useState<GameSummary[]>([]);
  const [game,setGame]=useState<ArenaGameState|null>(null);
  const [analysis,setAnalysis]=useState<AnalysisState|null>(null);
  const [error,setError]=useState<string|null>(null);
  const [loading,setLoading]=useState(true);
  const [query,setQuery]=useState("");
  const [filter,setFilter]=useState("all");
  const [ply,setPly]=useState(0);
  const [orientation,setOrientation]=useState<"white"|"black">("white");
  const [busy,setBusy]=useState(false);
  const [playing,setPlaying]=useState(false);
  const [panel,setPanel]=useState<"moves"|"details">("moves");

  useEffect(()=>{
    let stopped=false;
    let timer:number;
    let first=true;
    const load=async()=>{
      try {
        if(gameId){
          const [next,review]=await Promise.all([api<ArenaGameState>(`/games/${gameId}`),api<AnalysisState>(`/games/${gameId}/analysis`)]);
          if(stopped)return;
          setGame(next);setAnalysis(review);
          if(first){setPly(0);setOrientation(next.human_color);}
        }else{
          const body=await api<{games:GameSummary[]}>("/games");
          if(stopped)return;
          setGames(body.games);
        }
        first=false;setError(null);
      }catch(e){if(!stopped)setError((e as Error).message);}
      finally{if(!stopped){setLoading(false);timer=window.setTimeout(()=>{void load();},3000);}}
    };
    void load();
    return()=>{stopped=true;window.clearTimeout(timer);};
  },[gameId]);

  const maxPly=game?.moves.length??0;
  useEffect(()=>{
    if(!playing||ply>=maxPly)return;
    const timer=window.setTimeout(()=>setPly(p=>Math.min(p+1,maxPly)),1000);
    return()=>window.clearTimeout(timer);
  },[playing,maxPly,ply]);
  const visible=useMemo(()=>games.filter(g=>(filter==="all"||(filter==="finished"?g.status==="finished":filter==="analyzed"?g.analysis?.status==="complete":g.status!=="finished"))&&`${g.setup.model} ${providerName(g.setup.provider)} ${dayLabel(g.created_at)}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())),[games,filter,query]);
  const selectPly=(next:number)=>{setPlaying(false);setPly(Math.max(0,Math.min(next,maxPly)));};
  const requestAnalysis=async()=>{
    setBusy(true);setError(null);
    try{setAnalysis(await api<AnalysisState>(`/games/${gameId}/analysis`,{method:"POST",body:"{}"}));}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  };

  if(!gameId)return <div className="chess-desk archive-desk">
    <header className="desk-archive-heading"><div><span className="desk-overline">SUAS PARTIDAS</span><h1>Histórico</h1><p>{games.length} partidas salvas · {games.filter(g=>g.analysis?.status==="complete").length} análises concluídas</p></div><a className="desk-button primary" href="#jogar"><Icon name="play" size={15}/>Nova partida</a></header>
    <div className="desk-archive-toolbar"><div className="desk-filters" role="group" aria-label="Filtrar partidas">{[["all","Todas"],["finished","Encerradas"],["ongoing","Em andamento"],["analyzed","Analisadas"]].map(([value,label])=><button key={value} data-active={filter===value} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}{value==="all"&&<span>{games.length}</span>}</button>)}</div><label className="desk-search"><Icon name="search" size={16}/><input name="game-search" type="search" autoComplete="off" spellCheck={false} aria-label="Buscar partida" placeholder="Buscar modelo ou data…" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>
    {error&&<div className="desk-error" role="alert"><Icon name="alert" size={16}/><p>Não foi possível atualizar o histórico. Tentaremos novamente.<small>{error}</small></p></div>}
    <div className="desk-archive-table" aria-label="Histórico de partidas contra modelos">
      {loading?<div className="desk-loading-list" role="status" aria-label="Carregando histórico">{[0,1,2,3].map(n=><div key={n}/>)}</div>:visible.length===0?<div className="desk-archive-empty"><Icon name={games.length?"search":"grid"} size={32}/><h2>{games.length?"Nenhuma partida encontrada":"Seu histórico começa com uma partida"}</h2><p>{games.length?"Tente outro modelo, data ou filtro.":"Seus jogos e análises ficam guardados aqui."}</p>{games.length?<button className="desk-button" onClick={()=>{setQuery("");setFilter("all");}}>Limpar filtros</button>:<a className="desk-button primary" href="#jogar">Jogar agora<Icon name="arrow" size={15}/></a>}</div>:<table><thead><tr><th>Quando</th><th>Oponente</th><th>Resultado</th><th>Lances</th><th>Análise</th><th><span className="sr-only">Abrir partida</span></th></tr></thead><tbody>{visible.map(g=><tr key={g.id} className="desk-record">
        <td className="desk-record-date"><time dateTime={g.created_at}>{dayLabel(g.created_at)}<span>{timeLabel(g.created_at)}</span></time></td>
        <td className="desk-record-opponent"><div className="desk-record-identity"><ModelMark provider={g.setup.provider}/><div><a href={`#historico/${g.id}`} aria-label={`Rever partida contra ${modelName(g.setup.model)}, ${dayLabel(g.created_at)} às ${timeLabel(g.created_at)}`}>{modelName(g.setup.model)}</a><span><i className={`desk-color-dot ${g.human_color}`}/>Você de {g.human_color==="white"?"brancas":"pretas"}<span className="desk-mobile-count"> · {Math.ceil(g.plies/2)} lances</span></span></div></div></td>
        <td className="desk-record-result"><strong className={resultTone(g)}>{g.result?.score??"Em andamento"}</strong><span>{g.result?gameResult(g):"Pode continuar"}</span></td>
        <td className="desk-record-length"><strong>{Math.ceil(g.plies/2)}</strong><span>{g.plies} meios-lances</span></td>
        <td className="desk-record-analysis">{g.analysis?.status==="complete"?<><span className="desk-analysis-ready"><Icon name="check" size={13}/>Analisada</span><small>Stockfish · depth 20</small></>:g.status==="finished"?<><span>{analysisLabel(g.analysis?.status??"not_started")}</span>{g.analysis?.status==="running"&&<small>{g.analysis.completed} / {g.analysis.total} posições</small>}</>:<span className="desk-after-game">Após a partida</span>}</td>
        <td className="desk-record-open"><Icon name="chevron" size={16}/></td>
      </tr>)}</tbody></table>}
    </div>
    <footer className="desk-archive-footer"><span><Icon name="check" size={13}/>Todas as partidas são salvas automaticamente.</span><span>{visible.length} de {games.length} partidas</span></footer>
  </div>;

  if(!game)return <div className="chess-desk"><a className="desk-text-link" href="#historico"><Icon name="back" size={15}/>Histórico</a>{error?<div className="desk-error" role="alert"><p>Não foi possível abrir esta partida.<small>{error}</small></p></div>:<div className="desk-loading-board" role="status" aria-label="Carregando partida"/>}</div>;
  const position=game.positions?.[ply];
  const row=analysis?.positions[ply];
  const played=game.moves[ply-1];
  const previous=analysis?.positions[ply-1];
  const loss=played?moveLoss(previous,row,played.side):null;
  const reviewing=["running","queued","interrupted"].includes(analysis?.status??"");
  const finished=game.status==="finished";
  const topColor=orientation==="white"?"black":"white";
  const evaluation=cpValue(row);
  const whiteFill=evaluation==null?50:Math.max(4,Math.min(96,50+evaluation/12));

  return <div className="chess-desk review-desk">
    <header className="desk-review-heading"><div><a className="desk-text-link" href="#historico"><Icon name="back" size={14}/>Histórico</a><h1>Você <span>×</span> {modelName(game.setup.model)}</h1></div><div><span className={`desk-result ${resultTone(game)}`}>{game.result?.score&&<strong>{game.result.score}</strong>}{gameResult(game)}</span>{!finished?<button className="desk-button primary" onClick={()=>resume(game.id)}>Continuar<Icon name="arrow" size={14}/></button>:<a className="desk-icon-button" title="Baixar PGN" aria-label="Baixar PGN" href={`${API}/games/${game.id}/pgn`} download><Icon name="file" size={17}/></a>}</div></header>
    {error&&<div className="desk-error" role="alert"><Icon name="alert" size={15}/><p>{error}</p></div>}
    <div className="desk-layout">
      <section className="desk-board-column" aria-label="Rever posições da partida" tabIndex={0} onKeyDown={e=>{
        if((e.target as HTMLElement).closest("input,select,textarea,button,a,summary"))return;
        if(["ArrowLeft","ArrowRight","Home","End"].includes(e.key)){e.preventDefault();selectPly(e.key==="Home"?0:e.key==="End"?maxPly:ply+(e.key==="ArrowRight"?1:-1));}
      }}>
        <PlayerBar name={topColor===game.human_color?"Você":modelName(game.setup.model)} provider={game.setup.provider} human={topColor===game.human_color} color={topColor}/>
        <div className="desk-board-frame review-board-frame">{finished&&<div className="desk-eval-rail" role="img" aria-label={`Avaliação pela perspectiva das brancas: ${scoreLabel(row)}`} title="Vantagem das brancas"><span style={{height:`${whiteFill}%`,[orientation==="white"?"bottom":"top"]:0}}/></div>}<Board fen={position?.fen??game.fen} lastUci={position?.last_uci??null} orientation={orientation} animated={false}/></div>
        <PlayerBar name={orientation===game.human_color?"Você":modelName(game.setup.model)} provider={game.setup.provider} human={orientation===game.human_color} color={orientation} status={position?.check?"Xeque":undefined}/>
        <div className="desk-transport"><div><button className="desk-icon-button" aria-label="Posição inicial" disabled={ply===0} onClick={()=>selectPly(0)}><Icon name="first" size={17}/></button><button className="desk-icon-button" aria-label="Lance anterior" disabled={ply===0} onClick={()=>selectPly(ply-1)}><Icon name="back" size={17}/></button><button className="desk-icon-button transport-play" aria-label={playing&&ply<maxPly?"Pausar replay":"Reproduzir partida"} disabled={!maxPly} onClick={()=>{if(ply===maxPly)setPly(0);setPlaying(!playing||ply===maxPly);}}><Icon name={playing&&ply<maxPly?"pause":"play"} size={16}/></button><button className="desk-icon-button" aria-label="Próximo lance" disabled={ply===maxPly} onClick={()=>selectPly(ply+1)}><Icon name="arrow" size={17}/></button><button className="desk-icon-button" aria-label="Posição final" disabled={ply===maxPly} onClick={()=>selectPly(maxPly)}><Icon name="last" size={17}/></button></div><button className="desk-icon-button" aria-label="Virar tabuleiro" title="Virar tabuleiro" onClick={()=>setOrientation(c=>c==="white"?"black":"white")}><Icon name="flip" size={17}/></button></div>
        <label className="desk-timeline"><span>{ply} / {maxPly}</span><input name="replay-position" aria-label="Posição na partida" type="range" min={0} max={maxPly} value={ply} onChange={e=>selectPly(Number(e.target.value))}/><span>{position?.san??"Início"}</span></label>
        <details className="desk-position"><summary>FEN desta posição<Icon name="chevron" size={12}/></summary><div><code>{position?.fen??game.fen}</code><ClipboardButton value={position?.fen??game.fen}/></div></details>
      </section>
      <aside className="desk-side desk-review-side" aria-label="Análise e lances">
        <div className="desk-engine-heading"><div><Icon name="chart" size={17}/><h2>{analysis?.positions[0]?.engine??"Stockfish"}</h2><span>depth 20</span></div><span className={`desk-engine-state ${reviewing?"running":""}`} role="status">{analysisLabel(analysis?.status??"not_started")}</span></div>
        {finished?<>
          {reviewing&&<div className="desk-analysis-progress"><div><span>{analysisLabel(analysis?.status??"queued")}</span><strong>{analysis?.positions.length??0} / {analysis?.total??maxPly+1}</strong></div><progress aria-label="Progresso da análise" max={analysis?.total??maxPly+1} value={analysis?.positions.length??0}/><p>A análise continua mesmo com esta página fechada.</p></div>}
          <div className="desk-evaluation"><div><span>{ply?`Após ${position?.san??"o lance"}`:"Posição inicial"}</span><strong>{scoreLabel(row)}</strong><small>{row?.terminal?"Posição terminal":row?.depth?`Profundidade ${row.depth}`:"Aguardando avaliação"}</small></div><div><span>Melhor continuação</span><strong className="desk-bestmove">{row?.best_san??"—"}</strong><small>{row?.pv_san.slice(0,6).join(" ")||""}</small></div></div>
          {!!analysis?.positions.length&&<EvalGraph rows={analysis.positions} ply={ply} total={maxPly}/>}
          {played&&row&&<div className="desk-move-insight"><span>{played.actor==="human"?"Você jogou":"Modelo jogou"} <strong>{played.san}</strong></span><span>{loss!=null?`${loss} cp de perda`:"Avaliação de mate"}</span>{previous?.best_san&&previous.best_uci!==played.uci&&<small>Stockfish preferia {previous.best_san}</small>}</div>}
          {analysis?.status==="failed"&&<div className="desk-error" role="alert"><p>A análise parou; o progresso foi preservado.<small>{analysis.error}</small></p></div>}
          {!reviewing&&analysis?.status!=="complete"&&<div className="desk-review-retry"><button className="desk-button" disabled={busy} onClick={()=>void requestAnalysis()}><Icon name="refresh" size={14}/>{busy?"Iniciando…":analysis?.status==="failed"?"Retomar análise":"Analisar partida"}</button></div>}
        </>:<div className="desk-review-pending"><Icon name="clock" size={21}/><p>A análise começa quando a partida termina.</p></div>}
        <div className="desk-panel-tabs" role="group" aria-label="Conteúdo da revisão"><button aria-pressed={panel==="moves"} onClick={()=>setPanel("moves")}>Lances<span>{maxPly}</span></button><button aria-pressed={panel==="details"} onClick={()=>setPanel("details")}>Detalhes</button></div>
        {panel==="moves"?<MoveBook moves={game.moves} positions={game.positions} humanColor={game.human_color} selected={ply} analysis={analysis?.positions} onSelect={selectPly}/>:<div className="desk-review-details"><dl><div><dt>Provedor</dt><dd>{providerName(game.setup.provider)}</dd></div><div><dt>Modelo</dt><dd>{String(game.setup.model)}</dd></div><div><dt>Esforço</dt><dd>{String(game.setup.effort||"Padrão")}</dd></div><div><dt>Iniciada em</dt><dd>{dayLabel(game.created_at)}, {timeLabel(game.created_at)}</dd></div><div><dt>Chamadas por lance</dt><dd>{String(game.setup.max_rounds)}</dd></div></dl><p>Valores pela perspectiva das brancas. A perda compara avaliações entre posições; não é uma nota de precisão.</p>{row?.pv_san.length?<div><span className="desk-overline">LINHA PRINCIPAL</span><p className="desk-full-pv">{row.pv_san.join(" ")}</p></div>:null}<a className="desk-button" href={`${API}/games/${game.id}/pgn`} download><Icon name="file" size={14}/>Baixar PGN</a></div>}
        <div className="desk-review-footnote"><Icon name="check" size={12}/>{finished?"Análise local, salva com a partida":"Partida salva no histórico"}</div>
      </aside>
    </div>
  </div>;
}
