"""Static dashboard serving (production mode)."""

from aether_core.infrastructure.settings import AppSettings
from aether_core.interfaces.http import create_app
from fastapi.testclient import TestClient


def test_serves_dashboard_when_static_dir_set(tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html><body>Aether</body></html>", encoding="utf-8")

    settings = AppSettings(data_dir=tmp_path / "data", static_dir=static)
    with TestClient(create_app(settings)) as client:
        root = client.get("/", follow_redirects=True)
        assert root.status_code == 200
        assert "Aether" in root.text
        # API continua funcionando ao lado do estático
        assert client.get("/api/v1/health").status_code == 200


def test_no_static_dir_means_api_only(tmp_path):
    settings = AppSettings(data_dir=tmp_path / "data")
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/v1/health").status_code == 200
