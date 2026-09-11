from pathlib import Path
import json,subprocess,os,time,hashlib
r=Path('/home/maelrx/Documents/ChatGPT/Zugzwang');out=r/'out/isolated-winners-20260909'
assert not (out/'launch.json').exists(),'Already launched; never duplicate runs'
rows=json.loads((out/'selection.json').read_text());procs=[]
auth=json.loads(Path('/home/maelrx/.codex/auth.json').read_text())
assert auth.get('auth_mode')=='chatgpt' and not auth.get('OPENAI_API_KEY'),'Subscription-only execution required'
for row in rows:
 ws=Path(row['workspace']);assert not (ws/'.zugzwang/state.db').exists(),'Workspace already has evidence'
 assert hashlib.sha256((r/row['source']).read_bytes()).hexdigest()==row['source_sha256'],'Source drift'
for row in rows:
 ws=Path(row['workspace']);ws.mkdir(exist_ok=True)
 log=(out/f'run-{row["index"]:02d}.log').open('ab');cmd=[str(r/'.venv/bin/zugzwang'),'run',row['manifest'],'--workspace',str(ws),'--output','json'];env=os.environ.copy();env['PYTHONUNBUFFERED']='1'
 for key in ['ZGZ_MUSE_SINGLE_FLIGHT_LOCK','OPENAI_API_KEY','CODEX_API_KEY']:env.pop(key,None)
 p=subprocess.Popen(cmd,cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 procs.append({**row,'pid':p.pid,'launched_at':time.time(),'manifest_sha256':hashlib.sha256(Path(row['manifest']).read_bytes()).hexdigest(),'isolation':'model-only/v1'})
 (out/'launch.json').write_text(json.dumps(procs,indent=2))
print(json.dumps([{'index':x['index'],'pid':x['pid']} for x in procs]))
