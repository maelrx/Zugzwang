import json,subprocess,select,os,time
from pathlib import Path
result={}
try:
 Path('/tmp/zgw-guardrail-audit/write-canary').write_text('guardrail audit canary')
 result['write']='ALLOWED'
except OSError as exc:result['write']=type(exc).__name__
engine=subprocess.Popen(['/home/maelrx/.local/bin/stockfish'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
output=b''
try:
 engine.stdin.write(b'uci\nisready\nposition startpos\ngo depth 1\n');engine.stdin.flush()
 deadline=time.monotonic()+6
 while time.monotonic()<deadline and b'bestmove' not in output:
  if select.select([engine.stdout],[],[],.1)[0]:
   block=os.read(engine.stdout.fileno(),65536)
   if not block:break
   output+=block
 engine.stdin.write(b'quit\n');engine.stdin.flush()
 engine.wait(timeout=2)
finally:
 if engine.poll() is None:engine.kill();engine.wait()
result.update(engine_started=b'id name Stockfish' in output,has_bestmove=b'bestmove' in output,output=output.decode(errors='replace')[-850:])
print(json.dumps(result),flush=True)
