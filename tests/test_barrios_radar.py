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


def test_external_labels_are_used_only_if_they_help():
    pytest.importorskip("sklearn")
    rnd = random.Random(3)
    def rows(n, signal):
        out = []
        for _ in range(n):
            label = rnd.randint(0, 1)
            r = {f: rnd.random() for f in br.OPTICAL + br.RADAR + br.BUILDINGS}
            r["VH_diff"] = (label + rnd.random() * 0.5) if signal else rnd.random()
            r["label"] = label
            out.append(r)
        return out
    samples = {c: rows(40, True) for c in ("a", "b", "c")}       # pocas muestras locales
    external = rows(600, True)                                   # muchas de otra ciudad con la misma firma
    _, summary, _ = br.leave_one_city_out(samples, external)
    assert "optico_radar_externas" in summary
    assert summary["optico_radar_externas"]["f1_barrio"] >= summary["optico_radar"]["f1_barrio"] - 0.02


def test_load_external_groups_by_city(monkeypatch, tmp_path):
    import json
    poly = {"type": "Polygon", "coordinates": [[[36.8, -1.3], [36.81, -1.3], [36.81, -1.29], [36.8, -1.3]]]}
    f = tmp_path / "ext.geojson"
    f.write_text(json.dumps({"features": [
        {"geometry": poly, "properties": {"clase": "informal", "ciudad": "Nairobi"}},
        {"geometry": poly, "properties": {"clase": "formal", "ciudad": "Nairobi"}},
        {"geometry": poly, "properties": {"clase": "informal", "ciudad": "Eldoret"}}]}))
    monkeypatch.setattr(br, "EXTERNAL_FILE", str(f))
    groups = br.load_external()
    assert list(groups) == ["Nairobi"]          # Eldoret no tiene barrios comunes: queda afuera


def test_osm_polygons_from_ways_and_relations():
    pytest.importorskip("shapely")
    sq = [{"lon": 36.78, "lat": -1.31}, {"lon": 36.79, "lat": -1.31}, {"lon": 36.79, "lat": -1.30}, {"lon": 36.78, "lat": -1.31}]
    rel = {"type": "relation", "members": [
        {"role": "outer", "geometry": [{"lon": 36.85, "lat": -1.26}, {"lon": 36.86, "lat": -1.26}, {"lon": 36.86, "lat": -1.25}]},
        {"role": "outer", "geometry": [{"lon": 36.86, "lat": -1.25}, {"lon": 36.85, "lat": -1.26}]}]}
    open_way = {"type": "way", "geometry": sq[:3]}
    out = br.osm_polygons([{"type": "way", "geometry": sq}, rel, open_way])
    assert len(out) == 2 and {g["type"] for g in out} <= {"Polygon", "MultiPolygon"}


def test_overpass_query_targets_informal_tags_and_names():
    q = br.overpass_query(br.circle_bbox(-1.286, 36.817, 16000), ["Kibera", "Mathare"])
    assert '["residential"="informal"]' in q and "Kibera|Mathare" in q and q.strip().endswith("out geom;")


def test_osm_informal_survives_without_network(monkeypatch):
    monkeypatch.setattr(br.time, "sleep", lambda s: None)
    def down(*a, **k):
        raise br.requests.ConnectionError("sin red")
    monkeypatch.setattr(br.requests, "post", down)
    assert br.osm_informal(br.OSM_CITIES[0]) == []
