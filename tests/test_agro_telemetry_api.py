from datetime import date, timedelta
from flask import Flask
import agro_telemetry_api as module

def app():
    instance=Flask(__name__)
    instance.register_blueprint(module.agro_telemetry_api)
    return instance.test_client()

def test_missing_coordinates():
    assert app().get("/api/agro/telemetria").status_code == 400

def test_invalid_coordinates():
    assert app().get("/api/agro/telemetria?lat=200&lon=0").status_code == 400

def test_returns_daily_data_with_provenance(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"daily":{"time":["2025-01-01"],"precipitation_sum":[2.1]},
                    "daily_units":{"precipitation_sum":"mm"}}
    captured={}
    def fake_get(url,params,timeout):
        captured.update(params)
        return Response()
    monkeypatch.setattr(module.requests,"get",fake_get)
    response=app().get("/api/agro/telemetria?lat=-28.507&lon=-59.043&start=2025-01-01&end=2025-01-01")
    assert response.status_code == 200
    payload=response.get_json()
    assert payload["daily"]["precipitation_sum"] == [2.1]
    assert "precipitation_sum" in captured["daily"]
    assert "temperature_2m_mean" in captured["daily"]
    assert "model" in payload["data_kind"].lower()

def test_future_date_rejected():
    future=(date.today()+timedelta(days=2)).isoformat()
    response=app().get(f"/api/agro/telemetria?lat=0&lon=0&start={future}&end={future}")
    assert response.status_code == 400
