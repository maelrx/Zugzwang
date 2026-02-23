from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from zugzwang.api.routes import configs, dashboard, env, jobs, runs
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
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    _register_api_not_found_fallback(app)

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
    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="frontend")


def _register_api_not_found_fallback(app: FastAPI) -> None:
    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    def api_not_found(path: str) -> None:
        _ = path
        raise HTTPException(status_code=404, detail="Not Found")


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client-side routes while preserving API 404 semantics."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


app = create_app()
