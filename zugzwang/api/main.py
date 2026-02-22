from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from zugzwang.api.routes import configs, env, jobs, runs
from zugzwang.api.services.paths import project_root


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zugzwang API",
        version="0.1.0",
        description="HTTP adapter over Zugzwang engine services.",
    )
    _configure_cors(app)

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(configs.router, prefix="/api")
    app.include_router(env.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")

    _maybe_mount_frontend_dist(app)
    return app


def _configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _maybe_mount_frontend_dist(app: FastAPI) -> None:
    dist_dir = project_root() / "zugzwang-ui" / "dist"
    if not dist_dir.exists():
        return
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")


app = create_app()
