import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useSnapshot } from "@/lib/useSnapshot";
import { ageLabel, conditionLabel, modelLabel, parseRoute, routeFor, runState, runTitle } from "@/lib/presentation";
import type { DetailView, StatusFilter } from "@/lib/presentation";
import { useAppearance } from "@/lib/appearance";
import { TEXTURES } from "@/lib/textures";
import { RunsOverview } from "@/components/RunsOverview";
import { CompareView } from "@/components/CompareView";
import { AppearanceMenu } from "@/components/AppearanceMenu";
import { Icon } from "@/components/Icon";
const GameView = lazy(() => import("@/components/GameView").then(m => ({ default: m.GameView })));
const DeepView = lazy(() => import("@/components/DeepView").then(m => ({ default: m.DeepView })));
const EMPTY_RUNS: import("@/lib/types").Run[] = [];
function LoadingState() {
  return <div className="loading-state" role="status" aria-label="Carregando execuções"><div className="skeleton skeleton-title"/>{[1, 2, 3, 4, 5].map(n => <div key={n} className="skeleton skeleton-row"/>)}<span className="sr-only">Carregando dados do workspace</span></div>;
}
export default function App() {
  const { snap, loading, refreshing, error, refreshedAt, reload } = useSnapshot(15000);
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  useEffect(() => { const read = () => { setRoute(parseRoute(window.location.hash)); setComparing(false); }; window.addEventListener("hashchange", read); return () => window.removeEventListener("hashchange", read); }, []);
  const runs = snap?.runs ?? EMPTY_RUNS;
  const current = useMemo(() => runs.find(r => r.id === route.runId), [runs, route.runId]);
  const selectedRuns = useMemo(() => selected.flatMap(id => { const r = runs.find(r => r.id === id); return r ? [r] : []; }), [runs, selected]);
  const activeIds = selectedRuns.map(r => r.id);
  const back = () => { window.location.hash = ""; setRoute(parseRoute("")); setComparing(false); };
  const filter = (s: StatusFilter) => { back(); setStatus(s); };
  const toggle = (id: string) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev.filter(x => runs.some(r => r.id === x)), id].slice(0, 3));
  const date = snap?.generatedAt ? Date.parse(snap.generatedAt) : NaN;
  const stale = Number.isFinite(date) && (refreshedAt ?? date) - date > 120_000;
  const st = current ? runState(current) : null;
  const appearance = useAppearance();
  const texture = TEXTURES[appearance.texture];
  const textureStyle = texture.uri
    ? {
        backgroundImage: `url("${texture.uri}")`,
        backgroundSize: `${texture.tile}px`,
        mixBlendMode: appearance.theme === "light" ? texture.light.blend : texture.dark.blend,
        opacity: appearance.theme === "light" ? texture.light.opacity : texture.dark.opacity,
      }
    : undefined;
  return <>
    {textureStyle && <div className="texture-overlay" style={textureStyle} aria-hidden="true" />}
    <div className="app-shell">
    <a className="skip-link" href="#main-content">Ir para o conteúdo</a>
    <aside className="sidebar">
      <a className="brand" href="#" onClick={back}><span className="brand-mark" aria-hidden="true">Z<span>·</span></span><div><strong>Zugzwang</strong><span>Research workspace</span></div></a>
      <div className="workspace-label"><span className="workspace-avatar">L</span><div><strong>Workspace local</strong><span>Somente leitura</span></div></div>
      <nav className="sidebar-nav" aria-label="Navegação principal">
        <button className={!comparing && (Boolean(route.runId) || status !== "attention") ? "active" : ""} onClick={() => filter("all")}><Icon name="grid"/>Partidas<span className="nav-count">{runs.length}</span></button>
        <button className={!comparing && !route.runId && status === "attention" ? "active" : ""} onClick={() => filter("attention")}><Icon name="alert"/>Atenção<span className="nav-count">{runs.filter(r => runState(r).key === "attention").length}</span></button>
        <button className={comparing ? "active" : ""} onClick={() => setComparing(true)}><Icon name="compare"/>Comparar{selectedRuns.length > 0 && <span className="nav-count">{selectedRuns.length}</span>}</button>
      </nav>
      <div className="sidebar-context"><p className="eyebrow">Como explorar</p><ol><li><span>01</span>Encontre uma execução</li><li><span>02</span>Examine a partida</li><li><span>03</span>Confira as evidências</li></ol></div>
      <div className="sidebar-footer"><span className="local-dot"/>Dados locais e privados<p>Esta interface não inicia nem modifica execuções.</p></div>
    </aside>
    <div className="workspace-main"><header className="topbar"><div className="breadcrumb"><button onClick={back}>Workspace</button><Icon name="chevron" size={13}/><span>{comparing ? "Comparação" : route.runId ? "Execução" : "Biblioteca"}</span></div><div className="freshness" title={Number.isFinite(date) ? `Dados gerados em ${new Date(date).toLocaleString("pt-BR")}` : "Horário de geração não informado"}><i className={error || stale ? "warning" : ""}/><span>{error ? "Atualização indisponível" : Number.isFinite(date) ? `Dados ${ageLabel(date)}` : "Aguardando dados"}</span></div><AppearanceMenu/><button className="button compact" onClick={() => void reload()} disabled={refreshing} aria-label="Atualizar dados"><Icon name="refresh" size={15}/><span>{refreshing ? "Atualizando" : "Atualizar"}</span></button></header>
      <main id="main-content" className="main-content" tabIndex={-1}>
        {error && <div className="notice error" role="alert"><Icon name="alert"/><div><strong>{snap ? "A última leitura continua disponível" : "Não foi possível carregar as execuções"}</strong><p>{snap ? "A atualização falhou. Você pode continuar a análise e tentar novamente." : "Verifique se a fonte de dados do workspace está disponível e tente atualizar."}</p><details><summary>Detalhes de conexão</summary><code>{error} · /data/data.json</code></details></div><button className="button" onClick={() => void reload()}>Tentar novamente</button></div>}
        {loading && !snap ? <LoadingState/> : snap && (comparing ? <CompareView runs={selectedRuns} onBack={back}/> : route.runId ? current ? <>
          <div className="page-heading detail-heading"><div><button className="back-link" onClick={back}><Icon name="back" size={15}/>Todas as partidas</button><h1>{runTitle(current)}</h1><p className="lead">{modelLabel(current)}<span className="separator">·</span>{conditionLabel(current)}</p></div><div className="detail-state"><span className={`state-badge tone-${st!.tone}`} title={st!.detail}><i/>{st!.label}</span><span className="mono quiet-label">{current.id}</span></div></div>
          <nav className="detail-tabs" aria-label="Explorar execução">{([["game", "Partida"], ["analysis", "Análise"], ["evidence", "Evidências"]] as [DetailView, string][]).map(([v, label]) => <a key={v} href={routeFor(current.id, v, route.episode, route.ply)} aria-current={route.view === v ? "page" : undefined}>{label}</a>)}</nav>
          <Suspense fallback={<LoadingState/>}>{route.view === "evidence" ? <DeepView run={current}/> : <GameView key={`${current.id}:${route.view}`} run={current} view={route.view} route={route}/>}</Suspense>
        </> : <div className="empty-state"><Icon name="file" size={32}/><h1>Execução não encontrada</h1><p>Este link não corresponde às execuções da leitura atual.</p><button className="button primary" onClick={back}>Voltar à biblioteca</button></div> : <RunsOverview runs={runs} query={query} setQuery={setQuery} status={status} setStatus={setStatus} selected={activeIds} onSelect={toggle} onCompare={() => setComparing(true)}/>)}
      </main><footer className="workspace-footer"><span>Zugzwang · pesquisa verificável</span><span>Leitura automática a cada 15 s</span></footer>
    </div>
    </div>
  </>;
}
