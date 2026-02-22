from __future__ import annotations

import argparse

from zugzwang.ui.launch import launch_ui


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zugzwang-dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args(argv)
    return launch_ui(host=args.host, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
