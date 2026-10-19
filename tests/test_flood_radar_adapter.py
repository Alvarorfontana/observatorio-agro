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


def test_scene_diagnostics(monkeypatch):
    monkeypatch.setattr(adapter.radar, "flooding", lambda *a, **k: {"data": {
        "area_ha": 10, "series": [
            {"status": "sin dato", "datetime": "2026-10-01"},
            {"status": "válida", "datetime": "2026-10-03", "water_fraction": 0.2},
            {"status": "válida", "datetime": "2026-10-09", "water_fraction": 0.3},
        ]}})
    result = adapter.summarize([[0, 0], [0, 1], [1, 1]])
    assert result["scenes_found"] == 3
    assert result["scenes_valid"] == 2
    assert result["scenes_failed"] == 1
    assert len(result["series"]) == 2


def test_insufficient_scene_diagnostics(monkeypatch):
    monkeypatch.setattr(adapter.radar, "flooding", lambda *a, **k: {"data": {
        "series": [{"status": "sin dato", "datetime": "2026-10-01"}]}})
    result = adapter.summarize([[0, 0], [0, 1], [1, 1]])
    assert result["status"] == "sin dato"
    assert result["scenes_found"] == 1
    assert result["scenes_valid"] == 0
    assert result["scenes_failed"] == 1
