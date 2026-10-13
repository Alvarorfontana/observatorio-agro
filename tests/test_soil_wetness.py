"""Humedad de suelo NASA POWER: limpieza, percentil, categoría y ruta (NASA simulada)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import date, timedelta
import soil_wetness as sw
import research_connectors as c


def _daily(n=80, end=date(2026, 10, 10), root=0.30, top=0.25):
    days = [(end - timedelta(days=i)) for i in range(n)][::-1]
    k = lambda d: d.strftime('%Y%m%d')
    return {'GWETROOT': {k(d): root for d in days} | {k(days[0]): -999.0},
            'GWETTOP': {k(d): top for d in days},
            'GWETPROF': {k(d): 0.4 for d in days}}


def _monthly(octs):
    m = {}
    for i, v in enumerate(octs):
        y = 2006 + i
        m[f'{y}10'] = v; m[f'{y}05'] = 0.9; m[f'{y}13'] = 0.5
    return m


def test_categoria_por_percentil():
    assert [sw.category(p) for p in (5, 20, 50, 80, 95, None)] == \
        ['muy seco', 'más seco que lo normal', 'normal', 'más húmedo que lo normal', 'muy húmedo', None]


def test_resumen_seco_frente_a_su_historia():
    hist = [0.40 + 0.01 * i for i in range(20)]  # octubres de 0.40 a 0.59
    out = sw.summarize(_daily(root=0.30), _monthly(hist))
    assert out['date'] == '2026-10-10' and out['root_pct'] == 30.0 and out['top_pct'] == 25.0
    assert out['percentile'] == 0 and out['category'] == 'muy seco' and out['years'] == 20
    assert out['normal_pct'] == 49.5 and out['anomaly_pts'] == -19.5
    assert out['change_30d_pts'] == 0.0 and len(out['series']) == 75
    assert out['normal_range']['p10'] < out['normal_range']['p90']


def test_ignora_faltantes_y_sin_dato_falla():
    import pytest
    with pytest.raises(ValueError):
        sw.summarize({'GWETROOT': {'20261001': -999.0}}, {})


def test_ruta_humedad_nasa(monkeypatch):
    from api.index import app
    def fake(url, params=None, headers=None, scope='generic', organism=None):
        if 'daily' in url:
            return c.envelope({'properties': {'parameter': _daily()}}, url, scope, organism)
        return c.envelope({'properties': {'parameter': {'GWETROOT': _monthly([0.30] * 20)}}}, url, scope, organism)
    monkeypatch.setattr(c, 'external', fake)
    r = app.test_client().get('/api/fuentes/humedad-nasa?lat=-28.5&lon=-59')
    j = r.get_json()
    assert r.status_code == 200 and j['data']['category'] == 'normal' and j['organism'].startswith('NASA')
