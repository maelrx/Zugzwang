"""Private live snapshots; original failed runs and previous data stay preserved."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json,subprocess,time,sqlite3,yaml
ROOT=Path('/home/maelrx/Documents/ChatGPT/Zugzwang')
OUT=ROOT/'out/isolated-winners-20260909'
WEB=Path('/home/maelrx/Documents/ChatGPT/Zugzwang-webui-appearance/viewer-next/public/data/data.json')
PREFIX='window.ZUGZWANG_DATA = '

def snapshot(row):
 ws=Path(row['workspace']);target=OUT/f'live-{ws.name}.js'
 if not (ws/'.zugzwang/state.db').exists():return []
 result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/build_readonly_viewer.py'),'--workspace',str(ws),'--output',str(target),'--limit','5'],cwd=ROOT,capture_output=True,timeout=25)
 if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-500:])
 data=target.read_text().strip();data=data.removeprefix(PREFIX).rstrip(';');runs=json.loads(data)['runs']
 for run in runs:
  run['workspaceTag']='isolated-winners';run['executionIsolation']='model-only/v1'
  if not run.get('experiment') or run['experiment']=='Zugzwang run':
   manifest=yaml.safe_load(Path(row['manifest']).read_text());run['experiment']=manifest['metadata']['name'];run['task']=manifest['spec']['task']['config'];run['budget']=manifest['spec']['budget']
  for ep in run.get('episodes',[]):
   if run['status']=='RUNNING' and ep.get('result')=='capped':ep['result']='in_progress'
  with sqlite3.connect(f'file:{ws}/.zugzwang/state.db?mode=ro',uri=True) as con:
   status_counts=dict(con.execute('select status,count(*) from attempts group by status'))
  run['provider']['calls']=status_counts.get('completed',0)
  run['provider']['failures']=status_counts.get('failed',0)+status_counts.get('timeout_unknown',0)
 return runs

def main():
 historical=json.loads((OUT/'historical-snapshot.json').read_text())['runs']
 old_ids={'run_k8bUCj5PKd5Fx1fmXUmuWg','run_J_Jhlv_y2tbhMfJQQWfQHw','run_ZPXjsN3w4nh5mxK_02Twxg'}
 for run in historical:
  if run['id'] in old_ids:
   run['persistedStatusBeforeOperatorStop']=run['status'];run['status']='CANCELLED';run['operatorStop']='ZGW-0118 force-stop, preserved evidence'
 rows=json.loads((OUT/'selection.json').read_text())+json.loads((OUT/'selection-first-attempt.json').read_text())+[json.loads((OUT/'selection-v2.json').read_text())[4]]
 while True:
  try:
   with ThreadPoolExecutor(max_workers=5) as pool:groups=list(pool.map(snapshot,rows))
   fresh=[run for group in groups for run in group];ids={r['id'] for r in fresh};runs=fresh+[r for r in historical if r['id'] not in ids]
   runs.sort(key=lambda r:(r['status']=='RUNNING',r.get('startedAt') or ''),reverse=True)
   now=datetime.now(timezone.utc).isoformat();doc={'generatedAt':now,'workspace':'Luna high Fast isolated winners + preserved history','readOnly':True,'workOrder':'ZGW-0118','runs':runs,'summary':{'runs':len(runs),'evaluatedRuns':sum(bool(r.get('metrics')) for r in runs)}}
   tmp=WEB.with_name('.isolated-data.json.tmp');tmp.write_text(json.dumps(doc,ensure_ascii=False));tmp.replace(WEB)
   state=[{'id':r['id'],'status':r['status'],'plies':sum(len(e.get('moves',[])) for e in r.get('episodes',[]))} for r in fresh]
   (OUT/'live-health.json').write_text(json.dumps({'updated_at':now,'runs':state},indent=2));print(now,json.dumps(state),flush=True)
  except Exception as exc:print('snapshot error',str(exc),flush=True)
  time.sleep(8)
if __name__=='__main__':main()
