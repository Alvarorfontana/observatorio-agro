"""El Niño: lectores de fuentes (sin red) y servicios de la web."""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("enso_fuentes", os.path.join(ROOT, "scripts", "enso_fuentes.py"))
ef = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ef)

CPC_HTML = """<html><head><script>var x = "SON 1 2 3";</script></head><body>
<h2>Official NOAA CPC ENSO Probabilities</h2><p>Issued October 2026</p>
<table id="probabilities-table"><tr><th>Season</th><th>La Ni&ntilde;a</th><th>Neutral</th><th>El Ni&ntilde;o</th></tr>
<tr><td>SON</td><td>0</td><td>0</td><td>100</td></tr>
<tr><td>OND</td><td>0</td><td>0</td><td>100</td></tr>
<tr><td>AMJ</td><td>1</td><td>54</td><td>45</td></tr>
<tr><td>MJJ</td><td>13</td><td>70</td><td>17</td></tr>
<tr><td>JJA</td><td>5</td><td>5</td><td>5</td></tr>
</table></body></html>"""


def test_parse_cpc_table_and_issue():
    text = ef.html_text(CPC_HTML)
    rows = ef.parse_season_probs(text)
    assert [r["season"] for r in rows] == ["SON", "OND", "AMJ", "MJJ"]       # JJA no suma 100: se descarta
    assert rows[2] == {"season": "AMJ", "year": None, "la_nina": 1, "neutral": 54, "el_nino": 45}
    assert ef.issue_month(text) == "2026-10"


def test_parse_inline_table_with_years_and_percent():
    text = "Season La Niña Neutral El Niño OND 2026 0% 0% 100% NDJ 2026/27 0% 0% 100% AMJ 2027 2% 6% 92% MJJ 2027 9% 31% 60%"
    rows = ef.parse_season_probs(text)
    assert len(rows) == 4 and rows[0]["year"] == 2026 and rows[3]["el_nino"] == 60


def test_parse_rejects_pages_without_table():
    with pytest.raises(ValueError):
        ef.parse_season_probs("El Niño conditions are expected to continue. SON 2026.")


def test_parse_mei():
    lines = ["1979 2026"] + [f"{y} " + " ".join(["0.50"] * 12) for y in range(1979, 2026)] + ["2026 1.10 1.20 1.30 1.50 1.80 2.10 2.40 2.60 2.70 -999.00 -999.00 -999.00", "-999.00"]
    pts = ef.parse_mei("\n".join(lines))
    assert pts[-1] == {"bimestre": "2026-09", "mei": 2.7}


def test_seasonal_discovers_parameters(monkeypatch):
    calls = []

    class R:
        def __init__(self, code, body):
            self.status_code, self._b = code, body
        def json(self):
            return self._b

    def fake(url, params=None, **k):
        calls.append(params)
        if "monthly" in params and params["monthly"].startswith("precipitation_anomaly"):
            return R(400, {"reason": "Cannot initialize SeasonalVariable from invalid String value precipitation_anomaly"})
        if "monthly" in params:
            return R(200, {"monthly": {"time": ["2026-11", "2026-12"], "precipitation_mean_anomaly": [35.2, 61.0],
                                        "temperature_2m_mean_anomaly": [-0.4, -0.2]}})
        return R(500, {})
    monkeypatch.setattr(ef.requests, "get", fake)
    plan, d = ef.seasonal_point(-27.4, -58.8)
    assert plan == ("monthly", ["precipitation_mean_anomaly", "temperature_2m_mean_anomaly"])
    assert d["precipitation_mean_anomaly"] == [35.2, 61.0]
    ef.seasonal_point(-28.5, -59.0, plan)          # con el plan ya conocido, va directo
    assert len(calls) == 3


def test_run_all_survives_failures(monkeypatch):
    def boom():
        raise RuntimeError("caída")
    for name in ("cpc", "ccsr", "mei", "seasonal"):
        monkeypatch.setattr(ef, name, boom)
    d = ef.run_all()
    assert all(d[k]["estado"] == "sin dato" for k in ("cpc", "ccsr_iri", "mei", "estacional"))


def test_forecast_endpoints(monkeypatch):
    from flask import Flask
    import datastore
    import enso_forecast_api as api
    app = Flask(__name__)
    app.register_blueprint(api.enso_forecast_api)
    c = app.test_client()
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: None)
    assert c.get("/api/enso/pronostico").status_code == 503
    assert c.get("/api/enso/atmosfera").status_code == 503
    assert c.get("/api/enso/iri").get_json()["estado"] == "catalogado"
    fake = {"cpc": {"estado": "recibido"}, "ccsr_iri": {"estado": "recibido", "emitido": "2026-10",
                                                         "probabilidades": [{"season": "OND", "el_nino": 100}],
                                                         "graficos": {"intensidad": "https://x/strength_plot/2026/10"}}}
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: fake if name == "enso_pronostico.json" else None)
    assert c.get("/api/enso/pronostico").get_json()["cpc"]["estado"] == "recibido"
    j = c.get("/api/enso/iri").get_json()
    assert j["emitido"] == "2026-10" and j["probabilidades"][0]["el_nino"] == 100
