from __future__ import annotations

import argparse
import json
import sys

from zugzwang.evaluation.pipeline import evaluate_run_dir
from zugzwang.experiments.runner import ExperimentRunner
from zugzwang.infra.config import resolve_config
from zugzwang.infra.env import load_dotenv, validate_environment
from zugzwang.infra.logging import configure_logging
from zugzwang.ui.launch import launch_ui


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zugzwang")
    parser.add_argument("--log-level", default="INFO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--model-profile")
    run_parser.add_argument("--set", action="append", dest="overrides")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--resume-run-id")

    play_parser = subparsers.add_parser("play")
    play_parser.add_argument("--config", required=True)
    play_parser.add_argument("--model-profile")
    play_parser.add_argument("--set", action="append", dest="overrides")

    env_parser = subparsers.add_parser("env-check")
    env_parser.add_argument("--config", required=True)
    env_parser.add_argument("--model-profile")
    env_parser.add_argument("--set", action="append", dest="overrides")

    eval_parser = subparsers.add_parser("evaluate")
    eval_parser.add_argument("--run-dir", required=True)
    eval_parser.add_argument("--player-color", choices=["white", "black"], default="black")
    eval_parser.add_argument("--opponent-elo", type=float)
    eval_parser.add_argument("--elo-color-correction", type=float, default=0.0)
    eval_parser.add_argument("--output-filename", default="experiment_report_evaluated.json")

    ui_parser = subparsers.add_parser("ui")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8501)

    api_parser = subparsers.add_parser("api")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)
    api_parser.add_argument("--reload", action="store_true")
    return parser


def _run_command(args: argparse.Namespace) -> int:
    runner = ExperimentRunner(
        config_path=args.config,
        model_profile_path=args.model_profile,
        overrides=args.overrides,
        resume=bool(getattr(args, "resume", False)),
        resume_run_id=getattr(args, "resume_run_id", None),
    )
    if args.dry_run:
        print(json.dumps(runner.dry_run(), indent=2))
        return 0
    print(json.dumps(runner.run(), indent=2))
    return 0


def _play_command(args: argparse.Namespace) -> int:
    overrides = list(args.overrides or [])
    overrides.extend(
        [
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
        ]
    )
    runner = ExperimentRunner(
        config_path=args.config,
        model_profile_path=args.model_profile,
        overrides=overrides,
    )
    print(json.dumps(runner.run(), indent=2))
    return 0


def _env_check_command(args: argparse.Namespace) -> int:
    config = resolve_config(
        experiment_config_path=args.config,
        model_profile_path=args.model_profile,
        cli_overrides=args.overrides,
    )
    validate_environment(config)
    print("Environment check passed.")
    return 0


def _evaluate_command(args: argparse.Namespace) -> int:
    load_dotenv()
    try:
        payload = evaluate_run_dir(
            run_dir=args.run_dir,
            player_color=args.player_color,
            opponent_elo=args.opponent_elo,
            elo_color_correction=args.elo_color_correction,
            output_filename=args.output_filename,
        )
    except Exception as exc:
        print(f"Evaluation failed: {exc}")
        return 2
    print(json.dumps(payload, indent=2))
    return 0


def _ui_command(args: argparse.Namespace) -> int:
    return launch_ui(host=args.host, port=args.port)


def _api_command(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("FastAPI runtime is not installed. Install with: python -m pip install -e .[api]")
        return 2

    uvicorn.run("zugzwang.api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if args.command == "run":
        return _run_command(args)
    if args.command == "play":
        return _play_command(args)
    if args.command == "env-check":
        return _env_check_command(args)
    if args.command == "evaluate":
        return _evaluate_command(args)
    if args.command == "ui":
        return _ui_command(args)
    if args.command == "api":
        return _api_command(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
