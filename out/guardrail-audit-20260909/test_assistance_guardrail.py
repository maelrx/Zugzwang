"""Desired no-assistance guardrails: expected to FAIL against current adapter."""
import asyncio,json
from pathlib import Path
import pytest
from zgw_provider_codex_cli.adapter import CodexCliBackend
from zugzwang_cli.arena.loop import ArenaDecisionLoop
from zugzwang_cli.arena.positions import BoardFacade
from zugzwang_core.ports.model import ModelRef

@pytest.fixture
def observed(tmp_path):
 events=[
 {'type':'item.completed','item':{'id':'engine','type':'command_execution','command':'stockfish','status':'completed','exit_code':0,'aggregated_output':'info depth 18 score cp 30 pv e2e4\nbestmove e2e4'}},
 {'type':'item.completed','item':{'id':'final','type':'agent_message','text':json.dumps({'command':'board_finalize','arguments':{'node_id':'n0','action_id':'e2e4'}})}},
 {'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':10}},
 ]
 exe=tmp_path/'fake-codex';exe.write_text("#!/bin/sh\ncat <<'EVENTS'\n"+'\n'.join(json.dumps(e) for e in events)+"\nEVENTS\n");exe.chmod(0o755)
 calls=[]
 loop=ArenaDecisionLoop(game_id='audit-fake',board=BoardFacade(),backend=CodexCliBackend(executable=str(exe)),model_ref=ModelRef(backend='provider.codex_cli',provider='codex-cli',model='gpt-5.6-luna'),call_sink=calls.append)
 outcome=asyncio.run(loop.run())
 return outcome,calls

def test_engine_assisted_native_execution_must_not_be_committed(observed):
 outcome,_=observed
 assert outcome.status != 'COMMITTED', 'Engine-assisted native execution was silently accepted as a legal model move'

def test_native_execution_must_be_present_in_arena_evidence(observed):
 _,calls=observed
 assert 'command_execution' in json.dumps(calls), 'Arena evidence dropped native execution and its engine output'
