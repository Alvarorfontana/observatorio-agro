"""Una escena por fecha: la tesela que cubre el lote (bug visto con datos reales en el borde T21JUJ/T21JTJ)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import vegetation as veg

LOT = [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]


def item(i, dt, west, east):
    ring = [[west, -29.0], [east, -29.0], [east, -28.0], [west, -28.0], [west, -29.0]]
    return {'id': i, 'geometry': {'type': 'Polygon', 'coordinates': [ring]},
            'properties': {'datetime': dt, 'platform': 'sentinel-2b'}}


def test_keeps_full_tile_per_date():
    full = item('S2B_T21JUJ', '2026-10-02T13:56:59Z', -59.5, -58.5)
    half = item('S2B_T21JTJ', '2026-10-02T13:56:59Z', -60.5, -59.04)
    older = item('S2B_T21JUJ_old', '2026-09-22T13:56:59Z', -59.5, -58.5)
    out = veg.best_tiles([half, full, older], LOT)
    assert [o['id'] for o in out] == ['S2B_T21JUJ', 'S2B_T21JUJ_old'] and out[0]['_coverage'] == 1.0


def test_drops_tile_that_barely_touches():
    edge = item('S2B_edge', '2026-10-02T13:56:59Z', -60.5, -59.045)
    assert veg.best_tiles([edge], LOT) == []


class R:
    def __init__(self, d): self._d = d
    def json(self): return self._d


def test_ndvi_falls_back_to_modis(monkeypatch):
    import research_connectors as c
    def boom(*a, **k): raise ConnectionError('PC caído')
    monkeypatch.setattr(veg, 'ndvi_open', boom)
    seen = {}
    def get(url, params=None, headers=None, timeout=None):
        seen.update(params)
        return R({'scale': '0.0001', 'subset': [
            {'modis_date': 'A2026257', 'calendar_date': '2026-09-14', 'data': [6000, 7000, -3000]},
            {'modis_date': 'A2026273', 'calendar_date': '2026-09-30', 'data': [-3000]}]})
    monkeypatch.setattr(c, '_get', get)
    d = veg.ndvi_best(LOT)['data']
    assert d['fallback'] and 'Planetary Computer' in d['fallback_reason']
    assert d['valid_scenes'] == 1 and d['latest']['ndvi_mean'] == 0.65
    assert seen['band'] == '250m_16_days_NDVI' and seen['kmAboveBelow'] == 0 and d['window_km'] == 0.25
