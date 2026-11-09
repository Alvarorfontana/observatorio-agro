from datetime import date
from flask import Flask

from agentic.collectors.faostat import collect as collect_faostat
from agentic.collectors.nasa_power import collect as collect_nasa_power
from agentic.routes import dots_agentic_api


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payload)


def test_faostat_collector_normalizes_real_source_records():
    session = FakeSession({"data": [{
        "Area Code": "9", "Area": "Argentina", "Element Code": "2510",
        "Element": "Production", "Item": "Maize", "Item Code": "56",
        "Year": "2022", "Value": 59000000, "Unit": "t", "Flag": "A"
    }]})
    result = collect_faostat(session=session, end_year=2022)
    assert result["record_count"] == 1
    assert result["records"][0]["country"] == "Argentina"
    assert result["records"][0]["indicator"] == "production"
    assert session.calls[0][1]["area"] == "9,21,169,234"


def test_nasa_power_collector_labels_reference_points_and_missing_values():
    payload = {"properties": {"parameter": {
        "PRECTOTCORR": {"20260101": 4.2, "20260102": -999},
        "T2M": {"20260101": 22.1}
    }}}
    session = FakeSession(payload)
    result = collect_nasa_power(
        session=session, start_date=date(2026, 1, 1), end_date=date(2026, 1, 2)
    )
    assert result["record_count"] == 18
    assert result["records"][0]["spatial_method"] == "single_reference_point_not_national_average"
    assert any(r["status"] == "missing" for r in result["records"])


def test_agent_data_routes_return_empty_state_until_first_collection():
    app = Flask(__name__)
    app.register_blueprint(dots_agentic_api)
    response = app.test_client().get("/api/agentic/data/climate")
    assert response.status_code == 200
    assert response.get_json()["state"] == "not_collected"
    assert app.test_client().get("/api/agentic/runs/latest").get_json()["state"] == "not_run_yet"
