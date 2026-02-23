from __future__ import annotations

from pathlib import Path

from zugzwang.infra.env import load_dotenv


def test_load_dotenv_reads_utf8_bom_file(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    # Write with UTF-8 BOM prefix.
    env_path.write_text("ZAI_API_KEY=test-key\n", encoding="utf-8-sig")

    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    load_dotenv(env_path)

    import os

    assert os.environ.get("ZAI_API_KEY") == "test-key"


def test_load_dotenv_overrides_empty_env_value(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ZAI_API_KEY=test-key\n", encoding="utf-8")

    monkeypatch.setenv("ZAI_API_KEY", "")
    load_dotenv(env_path)

    import os

    assert os.environ.get("ZAI_API_KEY") == "test-key"
