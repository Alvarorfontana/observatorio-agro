"""Índices satelitales (catálogo abierto), radar Sentinel-1 y balance de agua ERA5."""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import vegetation as veg
import spectral, radar, water_balance as wb

LOT = [[-28.56, -58.71], [-28.56, -58.69], [-28.54, -58.69], [-28.54, -58.71]]
ITEM = {'id': 'S2B_X', 'properties': {'s2:processing_baseline': '05.11', 'datetime': '2026-10-02T13:00:00Z'}}


def test_catalog_has_many_s2_indices():
    s = spectral.catalog_summary()
    assert s['total'] >= 200 and set(spectral.DEFAULT) <= set(s['all'])


@pytest.mark.parametrize('name', list(spectral.DEFAULT))
def test_every_default_index_translates(name):
    e = spectral.expression(name, ITEM)
    assert 'B0' in e or 'B1' in e or 'B8A' in e
    assert not any(tok in e.split() for tok in ('N', 'R', 'G', 'S1'))


def test_expression_uses_reflectance_and_constants():
    e = spectral.expression('EVI', ITEM)
    assert '((B08-1000)/10000)' in e and '2.5' in e and '6.0' in e
    with pytest.raises(ValueError):
        spectral.expression('NO_EXISTE', ITEM)


def test_compute(monkeypatch):
    monkeypatch.setattr(veg, 'search_s2', lambda *a, **k: [ITEM | {'geometry': None}])
    monkeypatch.setattr(veg, 'best_tiles', lambda items, pts: items)
    monkeypatch.setattr(veg, 'scene_ndvi', lambda it, f: {'status': 'válida', 'item': it['id'], 'datetime': '2026-10-02'})
    monkeypatch.setattr(veg, '_pc_stats', lambda i, f, e: {'mean': 0.42, 'percentile_2': 0.1, 'percentile_98': 0.7})
    d = spectral.compute(LOT, ['NDVI', 'NBR', 'XX'])['data']
    assert [x['name'] for x in d['indices']] == ['NDVI', 'NBR'] and d['indices'][1]['domain'] == 'quemas'


def test_radar(monkeypatch):
    class R:
        def __init__(self, d): self._d = d
        def json(self): return self._d
    items = [{'id': f'S1_{i}', 'geometry': None, 'properties': {'datetime': f'2026-10-{i:02d}T09:00:00Z', 'platform': 'sentinel-1a'}} for i in (1, 13)]
    monkeypatch.setattr(c, '_post', lambda url, body, timeout=30: R({'features': items}))
    vals = {'S1_1': 0.01, 'S1_13': 0.08}
    def stats(item_id, feature, expression=None, asset=None):
        return {'mean': vals[item_id]} if expression else {'median': 0.1, 'count': 4000}
    monkeypatch.setattr(radar, '_stats', stats)
    d = radar.flooding(LOT)['data']
    assert d['latest']['water_fraction'] == 0.08 and d['latest']['vv_db_median'] == -10.0
    assert d['trend'] == 'el agua en el lote aumenta' and d['latest']['water_ha'] > 0


def test_water_balance_math():
    from datetime import date, timedelta
    t, p, e = [], [], []
    d0 = date(1991, 1, 1)
    for i in range((date(2026, 9, 30) - d0).days + 1):
        d = d0 + timedelta(days=i)
        t.append(d.isoformat())
        dry = d.year == 2026 and d.month >= 7
        p.append(0.5 if dry else 3.0 + (d.year % 5) * 0.2)
        e.append(4.0)
    out = wb.analyze_series({'time': t, 'precipitation_sum': p, 'et0_fao_evapotranspiration': e})
    assert out['last_month'] == 'sep 2026'
    assert out['spei']['3']['index'] < -1.5 and 'sequía' in out['spei']['3']['class']
    assert out['recent'][-1]['balance_mm'] == round(30 * 0.5 - 30 * 4.0)
    assert out['annual'][-1]['year'] == 2025


def test_water_balance_short_series():
    with pytest.raises(ValueError):
        wb.analyze_series({'time': ['2026-01-01'], 'precipitation_sum': [1], 'et0_fao_evapotranspiration': [1]})
