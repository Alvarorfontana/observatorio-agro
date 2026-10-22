"""Productos Copernicus y Timelapse: clasificación, interpretación y rutas, sin red."""
import base64
import json

import pytest
from flask import Flask

import copernicus_interpret as ci
import copernicus_products as cp
import copernicus_routes as cr
import pngmini
import timelapse_history as th

POLY = [[-28.50, -59.10], [-28.50, -59.02], [-28.45, -59.06]]


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(cr.copernicus_api)
    return app.test_client()


class _Resp:
    ok = True
    status_code = 200

    def __init__(self, content=b"", payload=None):
        self.content, self._payload = content, payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def _fake_sh(url, json=None, headers=None, timeout=None):
    if url.endswith("/search"):
        return _Resp(payload={"features": [{"properties": {"datetime": "2026-10-15T09:00:00Z"}}]})
    w, h = json["output"]["width"], json["output"]["height"]
    script, data = json["evalscript"], json["input"]["data"][0]
    if "127.5" in script:  # NDVI codificado: período viejo 0,1 y nuevo 0,6
        e = 140 if data["dataFilter"]["timeRange"]["from"] < "2026" else 204
        rows = [[(e, e, e, 255)] * w for _ in range(h)]
    else:
        kind = {"sentinel-1-grd": "s1_water", "sentinel-3-slstr-l2": "lst"}.get(data["type"])
        if not kind:
            kind = "aerosol" if "AER_AI" in script else "no2" if '"NO2"' in script else "co"
        col = ci.MAP_CLASSES[kind]["classes"][0][0]
        rows = [[tuple(col) + (255,)] * w for _ in range(h)]
    return _Resp(pngmini.encode_rgba(w, h, rows))


def _reading(resp):
    return json.loads(base64.b64decode(resp.headers["X-DOTS-Reading"]))


@pytest.mark.parametrize("kind", ["ndvi_change", "s1_water", "lst", "co", "no2", "aerosol"])
def test_products_return_png_and_reading(client, monkeypatch, kind):
    monkeypatch.setattr(cr, "_cdse_token", lambda: "t")
    monkeypatch.setattr(cp.requests, "post", _fake_sh)
    start = "2026-10-01" if kind in ("co", "no2", "aerosol") else "2026-09-01"
    r = client.post("/api/copernicus/map", json={"polygon": POLY, "index": kind, "start": start, "end": "2026-10-22"})
    assert r.status_code == 200 and r.data.startswith(b"\x89PNG")
    reading = _reading(r)
    assert reading["lines"] and reading["source"].startswith("Copernicus")
    assert abs(sum(c["pct"] for c in reading["stats"]["classes"]) - 100) < 0.5


def test_ndvi_change_detects_gain(client, monkeypatch):
    monkeypatch.setattr(cr, "_cdse_token", lambda: "t")
    monkeypatch.setattr(cp.requests, "post", _fake_sh)
    r = client.post("/api/copernicus/map", json={"polygon": POLY, "index": "ndvi_change",
                                                 "start": "2026-09-01", "end": "2026-10-22"})
    reading = _reading(r)
    assert reading["stats"]["classes"][4]["pct"] == 100.0
    assert any("pasó de 0,10 a 0,60" in line for line in reading["lines"])


def test_gases_limit_period(client, monkeypatch):
    monkeypatch.setattr(cr, "_cdse_token", lambda: "t")
    r = client.post("/api/copernicus/map", json={"polygon": POLY, "index": "co",
                                                 "start": "2026-08-01", "end": "2026-10-22"})
    assert r.status_code == 400


def test_regional_marks_parcel_value(client, monkeypatch):
    monkeypatch.setattr(cr, "_cdse_token", lambda: "t")
    monkeypatch.setattr(cp.requests, "post", _fake_sh)
    r = client.post("/api/copernicus/map", json={"polygon": POLY, "index": "lst",
                                                 "start": "2026-09-01", "end": "2026-10-22"})
    assert _reading(r)["stats"]["extra"]["parcel"]["label"] == "Fresco"


def test_report_accepts_map_and_reading(client, monkeypatch):
    monkeypatch.setattr(cr, "_cdse_token", lambda: "t")
    monkeypatch.setattr(cp.requests, "post", _fake_sh)
    m = client.post("/api/copernicus/map", json={"polygon": POLY, "index": "s1_water",
                                                 "start": "2026-09-01", "end": "2026-10-22"})
    r = client.post("/api/copernicus/report", json={
        "polygon": POLY, "scenes": [], "collection": "sentinel-1-grd", "start": "2026-09-01", "end": "2026-10-22",
        "map_png": base64.b64encode(m.data).decode(), "map_index": "s1_water", "map_reading": _reading(m)})
    assert r.status_code == 200 and r.data.startswith(b"%PDF")


def test_timelapse_route(client, monkeypatch):
    sent = {}

    def fake(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json)
        g = json["grid"]["dimensions"]
        return _Resp(pngmini.encode_rgba(g["width"], g["height"], [[(80, 110, 60, 255)] * g["width"]] * g["height"]))

    monkeypatch.setattr(th.veg, "gee_token", lambda: ("proj", "tok"))
    monkeypatch.setattr(th.requests, "post", fake)
    r = client.post("/api/historia/timelapse", json={"polygon": POLY, "year": 1990})
    assert r.status_code == 200 and sent["url"].endswith("/projects/proj/image:computePixels")
    assert sent["body"]["grid"]["crsCode"] == "EPSG:4326"
    assert client.post("/api/historia/timelapse", json={"polygon": POLY, "year": 2030}).status_code == 400
