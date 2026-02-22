from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from zugzwang.ui.services.paths import project_root


def launch_ui(host: str = "127.0.0.1", port: int = 8501) -> int:
    if importlib.util.find_spec("streamlit") is None:
        print("Streamlit is not installed. Install with: python -m pip install -e .[ui]")
        return 2

    app_path = Path(__file__).with_name("app.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]
    return subprocess.call(command, cwd=str(project_root()))
