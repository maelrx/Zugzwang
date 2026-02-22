from __future__ import annotations

import argparse

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zugzwang-dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print("FastAPI runtime is not installed. Install with: python -m pip install -e .[api]")
        return 2

    uvicorn.run("zugzwang.api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
