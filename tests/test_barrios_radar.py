"""Barrios populares por radar: partes que no necesitan red ni Earth Engine."""
import importlib.util
import os
import random

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("barrios_radar", os.path.join(ROOT, "scripts", "barrios_radar.py"))
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)


def test_circle_bbox_is_about_30_km():
    w, s, e, n = br.circle_bbox(-28.5, -59.0)
    assert round((n - s) * 111.32) == 30 and w < -59.0 < e


def test_clean_polygons_keeps_only_nearby_valid_shapes():
    pytest.importorskip("shapely")
    near = {"type": "Polygon", "coordinates": [[[-59.0, -28.5], [-58.99, -28.5], [-58.99, -28.49], [-59.0, -28.5]]]}
    far = {"type": "Polygon", "coordinates": [[[-50.0, -20.0], [-49.9, -20.0], [-49.9, -19.9], [-50.0, -20.0]]]}
    gj = {"features": [{"geometry": near, "properties": {"nombre": "x"}}, {"geometry": far}, {"geometry": None}]}
    out = br.clean_polygons(gj, br.circle_bbox(-28.5, -59.0))
    assert len(out) == 1 and out[0]["type"] == "Polygon"


def test_renabap_falls_back_to_local_file(monkeypatch, tmp_path):
    pytest.importorskip("shapely")
    import json
    f = tmp_path / "renabap.geojson"
    f.write_text(json.dumps({"features": [{"geometry": {"type": "Polygon", "coordinates": [
        [[-59.0, -28.5], [-58.99, -28.5], [-58.99, -28.49], [-59.0, -28.5]]]}}]}))
    monkeypatch.setattr(br, "RENABAP_FILE", str(f))
    monkeypatch.setattr(br, "_RENABAP_ALL", None)
    monkeypatch.setattr(br.time, "sleep", lambda s: None)

    def down(*a, **k):
        raise br.requests.ConnectionError("sin red")
    monkeypatch.setattr(br.requests, "get", down)
    polys, src = br.renabap(br.circle_bbox(-28.5, -59.0))
    assert src == "archivo" and len(polys) == 1


def test_leave_one_city_out_shows_radar_gain():
    pytest.importorskip("sklearn")
    rnd = random.Random(1)
    samples = {}
    for city in ("a", "b", "c", "d"):
        rows = []
        for _ in range(120):
            label = rnd.randint(0, 1)
            r = {f: rnd.random() for f in br.OPTICAL + br.RADAR}   # óptico sin señal
            r["VVt_ent"] = label + rnd.random() * 0.4                  # la textura de radar separa las clases
            r["label"] = label
            rows.append(r)
        samples[city] = rows
    per_city, summary, importance = br.leave_one_city_out(samples)
    assert len(per_city) == 4
    assert summary["optico_radar"]["f1_barrio"] > summary["optico"]["f1_barrio"] + 0.2
    assert importance[0]["capa"] == "VVt_ent"


def test_barrios_endpoint(monkeypatch):
    from flask import Flask
    import datastore
    from poblacion import routes
    app = Flask(__name__)
    app.register_blueprint(routes.bp)
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: None)
    j = app.test_client().get("/api/poblacion/barrios").get_json()
    assert j["data"] is None and "GitHub Actions" in j["error"]
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: {"places": [], "model": {}})
    j = app.test_client().get("/api/poblacion/barrios").get_json()
    assert j["image_base"].startswith("https://raw.githubusercontent.com/")


def test_final_model_prefers_buildings_only_when_better():
    assert br.choose_final({"optico_radar": {"f1_barrio": 0.7}, "optico_radar_edificios": {"f1_barrio": 0.75}}) == "optico_radar_edificios"
    assert br.choose_final({"optico_radar": {"f1_barrio": 0.7}, "optico_radar_edificios": {"f1_barrio": 0.7}}) == "optico_radar"
    assert br.choose_final({"optico_radar": {"f1_barrio": 0.7}, "optico_radar_edificios": {"f1_barrio": None}}) == "optico_radar"
