import importlib
import sys


def vision_client(monkeypatch):
    for key in ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DOTS_VISION_ACTIVA", "1")
    sys.path.insert(0, ".")
    module = importlib.import_module("vision_api")
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(module.vision_api)
    app.config["TESTING"] = True
    return app.test_client()


def test_vision_status_reports_missing_external_credentials(monkeypatch):
    client = vision_client(monkeypatch)
    response = client.get("/api/fuentes/vision/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "configuration_required"
    assert "RUNPOD_ENDPOINT_ID" in data["missing_environment"]


def test_upload_url_rejects_non_video_before_storage_access(monkeypatch):
    client = vision_client(monkeypatch)
    response = client.post("/api/fuentes/vision/upload-url",
                           json={"filename": "dataset.zip", "size": 1024})
    assert response.status_code == 400
    assert "Formato" in response.get_json()["error"]


def test_upload_url_rejects_video_larger_than_limit(monkeypatch):
    client = vision_client(monkeypatch)
    response = client.post("/api/fuentes/vision/upload-url",
                           json={"filename": "rode o.mp4", "size": 101 * 1024 * 1024})
    assert response.status_code == 413


def test_analyze_rejects_untrusted_object_key(monkeypatch):
    client = vision_client(monkeypatch)
    response = client.post("/api/fuentes/vision/analyze",
                           json={"object_key": "../private/video.mp4"})
    assert response.status_code == 400


def test_vision_is_paused_by_default(monkeypatch):
    client = vision_client(monkeypatch)
    monkeypatch.delenv("DOTS_VISION_ACTIVA", raising=False)
    assert client.get("/api/fuentes/vision/status").get_json()["status"] == "pausado"
    response = client.post("/api/fuentes/vision/upload-url", json={"filename": "a.mp4", "size": 10})
    assert response.status_code == 503
