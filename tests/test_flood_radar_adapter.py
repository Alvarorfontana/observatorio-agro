import flood_radar_adapter as adapter


def test_aggregate_change_is_not_pixelwise(monkeypatch):
    def fake(*args, **kwargs):
        return {"data": {"area_ha": 100, "series": [
            {"status": "válida", "datetime": "2026-10-01", "water_fraction": .1},
            {"status": "válida", "datetime": "2026-10-10", "water_fraction": .3},
        ]}}
    monkeypatch.setattr(adapter.radar, "flooding", fake)
    result = adapter.summarize([[0, 0], [0, 1], [1, 1]])
    assert result["estimated_net_water_change_ha"] == 20
    assert result["status"] == "AGGREGATE_CHANGE_UNVALIDATED"
    assert "area_ha" not in result
    assert result["change_map_url"] is None


def test_insufficient_scenes(monkeypatch):
    monkeypatch.setattr(adapter.radar, "flooding", lambda *a, **k: {"data": {"series": []}})
    assert adapter.summarize([[0, 0], [0, 1], [1, 1]])["status"] == "sin dato"
