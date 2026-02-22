from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from zugzwang.api.main import create_app


def test_frontend_routes_fallback_to_index_html(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path
    dist_dir = project_root / "zugzwang-ui" / "dist"
    dist_dir.mkdir(parents=True)
    index_content = "<html><body>qa-spa-index</body></html>"
    (dist_dir / "index.html").write_text(index_content, encoding="utf-8")

    monkeypatch.setattr("zugzwang.api.main.project_root", lambda: project_root)
    app = create_app()
    client = TestClient(app)

    deep_link = client.get("/runs/some-run-id")
    assert deep_link.status_code == 200
    assert "qa-spa-index" in deep_link.text


def test_unknown_api_paths_remain_404_json(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path
    dist_dir = project_root / "zugzwang-ui" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>qa-spa-index</body></html>", encoding="utf-8")

    monkeypatch.setattr("zugzwang.api.main.project_root", lambda: project_root)
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/unknown-path")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
