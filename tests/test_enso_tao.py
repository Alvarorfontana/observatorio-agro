"""Boyas TAO: lectura del CSV de ERDDAP, perfiles e isoterma de 20 °C (sin red)."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("enso_tao", os.path.join(ROOT, "scripts", "enso_tao.py"))
et = importlib.util.module_from_spec(spec)
spec.loader.exec_module(et)

CSV = """station,longitude,time,depth,T_20
,degrees_east,UTC,m,degree_C
0n140w,220.0,2026-09-20T12:00:00Z,1.0,28.0
0n140w,220.0,2026-09-20T12:00:00Z,100.0,22.0
0n140w,220.0,2026-09-20T12:00:00Z,140.0,18.0
0n140w,220.0,2026-09-21T12:00:00Z,1.0,28.2
0n140w,220.0,2026-09-21T12:00:00Z,100.0,22.2
0n140w,220.0,2026-09-21T12:00:00Z,140.0,18.2
0n165e,165.0,2026-09-21T12:00:00Z,1.0,29.0
0n165e,165.0,2026-09-21T12:00:00Z,100.0,NaN
"""


def test_parse_and_profiles():
    rows = et.parse_csv(CSV)
    assert len(rows) == 8 and rows[0]["longitude"] == 220.0 and rows[-1]["T_20"] is None
    now = et.profiles_now(rows)
    assert now[220.0]["perfil"] == {1.0: 28.1, 100.0: 22.1, 140.0: 18.1}
    assert now[220.0]["desde"] == "2026-09-20" and now[220.0]["hasta"] == "2026-09-21"
    assert now[165.0]["perfil"] == {1.0: 29.0}


def test_isotherm_and_labels():
    assert et.isotherm_depth({1.0: 28.0, 100.0: 22.0, 140.0: 18.0}) == 120.0
    assert et.isotherm_depth({1.0: 19.0, 50.0: 15.0}) is None
    assert et.lon_label(220.0) == "140° O" and et.lon_label(165.0) == "165° E" and et.lon180(265.0) == -95.0


def test_build_with_fake_server(monkeypatch, tmp_path):
    monkeypatch.setattr(et, "CLIMA_CACHE", str(tmp_path / "clima.json"))
    lons = (147.0, 165.0, 220.0, 250.0, 337.0)
    def fake(query, timeout=300):
        if "orderByMean" in query:
            return [{"longitude": l, "depth": d, "T_20": t} for l in lons for d, t in ((1.0, 27.0), (100.0, 21.0), (140.0, 17.0))]
        return [{"station": "x", "longitude": l, "time": "2026-09-21T12:00:00Z", "depth": d, "T_20": t + (2 if 230 < l < 300 else -1)}
                for l in lons for d, t in ((1.0, 27.0), (100.0, 21.0), (140.0, 17.0))]
    monkeypatch.setattr(et, "fetch_csv", fake)
    data = et.build()
    assert [b["nombre"] for b in data["boyas"]] == ["147° E", "165° E", "140° O", "110° O"]
    assert data["resumen"]["anom_este_0_150m"] == 2.0 and data["resumen"]["anom_oeste_80_200m"] == -1.0
    assert all(b["longitud"] != 337.0 for b in data["boyas"])   # la boya del Atlántico queda afuera
    b = data["boyas"][3]
    assert b["isoterma20_m"] > b["isoterma20_normal_m"]          # termoclina más profunda en el este: El Niño
    assert os.path.exists(tmp_path / "clima.json")


def test_tao_endpoint(monkeypatch):
    from flask import Flask
    import datastore
    import enso_forecast_api as api
    app = Flask(__name__)
    app.register_blueprint(api.enso_forecast_api)
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: None)
    assert app.test_client().get("/api/enso/tao").status_code == 503
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: {"boyas": [1]} if name == "enso_tao.json" else None)
    assert app.test_client().get("/api/enso/tao").get_json()["boyas"] == [1]
