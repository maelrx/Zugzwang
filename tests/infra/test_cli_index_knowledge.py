from __future__ import annotations

import json

from zugzwang.cli import main


def test_cli_index_knowledge_command_emits_summary(capsys) -> None:
    code = main(["index-knowledge", "--sources", "eco", "endgames"])

    assert code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["chunk_count"] > 0
    assert payload["chunk_count_by_source"]["eco"] > 0
    assert payload["chunk_count_by_source"]["endgames"] > 0
