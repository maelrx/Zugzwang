from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading,json,subprocess,importlib.util,os,signal
root=Path('/home/maelrx/Documents/ChatGPT/Zugzwang/out/guardrail-isolation-20260909/deployed-real-codex');root.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('zgw_isolation','/home/maelrx/Documents/ChatGPT/Zugzwang/plugins/provider-codex-cli/src/zgw_provider_codex_cli/isolation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"models":[],"data":[]}')
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
  if len(requests)>3:
   self.send_response(400);self.end_headers();return
  if len(requests)==1:
   item={'type':'function_call','id':'fc_attack','call_id':'call_attack','name':'exec_command','arguments':json.dumps({'cmd':'echo SHOULD_NOT_EXECUTE','workdir':str(root)})}
  else:
   item={'type':'message','id':'msg_ok','role':'assistant','status':'completed','content':[{'type':'output_text','text':'{"command":"board_finalize","arguments":{"node_id":"n0","action_id":"e2e4"}}','annotations':[]}]}
  response={'id':'resp_probe','object':'response','created_at':0,'status':'completed','model':'gpt-5.6-luna','output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
  events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},{'type':'response.output_item.added','output_index':0,'item':item},{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':response}]
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  for event in events:self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())
server=ThreadingHTTPServer(('127.0.0.1',4196),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
cmd=['/home/maelrx/.local/bin/codex','exec','--json','--ephemeral','--skip-git-repo-check','-s','read-only','-C',str(root),'-m','gpt-5.6-luna',*module.model_only_args(),'-c','model_provider="guardrail_probe"','-c','model_providers.guardrail_probe={name="Local guardrail probe",base_url="http://127.0.0.1:4196/v1",wire_api="responses",requires_openai_auth=false}','Perform the requested response.']
p=subprocess.Popen(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
try:out,err=p.communicate(timeout=35)
except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
server.shutdown()
events=[]
for line in out.splitlines():
 try:events.append(json.loads(line))
 except ValueError:pass
executed=[e for e in events if isinstance(e.get('item'),dict) and e['item'].get('type') in ['command_execution','mcp_tool_call','web_search']]
toolsets=[[t.get('name',t.get('type')) for t in r.get('tools',[])] for r in requests]
result={'exit_code':p.returncode,'requests':len(requests),'toolsets':toolsets,'executed':executed,'stdout':out,'stderr':err}
(root/'result.json').write_text(json.dumps(result,indent=2));(root/'requests.json').write_text(json.dumps(requests,indent=2))
print(json.dumps({'exit_code':p.returncode,'requests':len(requests),'toolsets':toolsets,'executed':executed,'stdout':out[-1600:]},indent=2))
assert requests and all(not r.get('tools') for r in requests),'Tool surface is not empty'
assert not executed,'Native command was executed despite tools-off'
# The injected command must be returned to the fake model as unsupported, not run.
assert any('unsupported' in json.dumps(r).lower() or 'unknown tool' in json.dumps(r).lower() for r in requests[1:]),'No explicit refusal received'
