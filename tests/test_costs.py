"""Costos, logística y margen con red simulada (los servicios reales se prueban en el sitio publicado)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import costs as cs

P = {'heads': 100, 'sale_kg': 400, 'price_kg': 2000, 'shrink_pct': 5, 'commission_pct': 4,
     'health_head': 10000, 'feed_head': 20000, 'labor_month': 500000, 'rent_ha': 30000,
     'freight_km': 2500, 'truck_heads': 40, 'area_ha': 250}


class R:
    def __init__(self, d): self._d = d
    def json(self): return self._d


def test_margin_math():
    m = cs.margin(cs.clean(P), km=300)
    assert m['kg_sold'] == 38000 and m['gross'] == 76_000_000
    assert m['trips'] == 3 and m['freight'] == 2_250_000            # 3 viajes × 300 km × 2500
    costs = 3_040_000 + 3_000_000 + 6_000_000 + 7_500_000 + 2_250_000
    assert m['costs'] == costs and m['net'] == 76_000_000 - costs
    assert m['net_ha'] == round((76_000_000 - costs) / 250)
    be = (3_000_000 + 6_000_000 + 7_500_000 + 2_250_000) / (38000 * 0.96)
    assert abs(m['breakeven_price_kg'] - be) < 0.1


def test_missing_values_are_none_not_zero():
    m = cs.margin(cs.clean({'heads': 50, 'sale_kg': 380}), km=None)
    assert m['gross'] is None and m['net'] is None and m['freight'] is None


def test_validation():
    with pytest.raises(ValueError): cs.clean({'heads': -1})
    with pytest.raises(ValueError): cs.clean({'price_kg': 'abc'})
    with pytest.raises(ValueError): cs.clean({'shrink_pct': 40})


def test_route_fallback_is_marked_estimated(monkeypatch):
    def boom(*a, **k): raise ConnectionError
    monkeypatch.setattr(c, '_get', boom)
    r = cs.route((-28.5, -59.0), (-27.47, -58.83))
    assert r['estimated'] and 'estimada' in r['method'] and 100 < r['km'] < 200


def test_analyze_end_to_end(monkeypatch):
    def get(url, params=None, headers=None, timeout=None):
        if 'nominatim' in url: return R([{'lat': '-27.47', 'lon': '-58.83', 'display_name': 'Corrientes, Argentina'}])
        if 'osrm' in url: return R({'code': 'Ok', 'routes': [{'distance': 152300, 'duration': 7200,
                                   'geometry': {'coordinates': [[-59.0, -28.5], [-58.83, -27.47]]}}]})
        if 'oficial' in url: return R({'compra': 1000, 'venta': 1050, 'fechaActualizacion': '2026-10-09'})
        if 'mayorista' in url: return R({'venta': 1020})
        raise AssertionError(url)
    monkeypatch.setattr(c, '_get', get)
    d = cs.analyze(-28.5, -59.0, 'Corrientes', params=P)['data']
    assert d['logistics']['km'] == 152.3 and not d['logistics']['estimated'] and d['logistics']['line'][0] == [-28.5, -59.0]
    assert d['exchange']['oficial_venta'] == 1050 and d['margin']['net_usd'] is not None
    assert len(d['sensitivity']) == 5 and d['sensitivity'][2]['price_factor'] == 1.0
    assert d['missing'] == []


def test_route_endpoint(monkeypatch):
    from api.index import app
    monkeypatch.setattr(c, '_get', lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    r = app.test_client().post('/api/fuentes/costos', json={'lat': -28.5, 'lon': -59.0, 'params': {'heads': 10, 'sale_kg': 400, 'price_kg': 2000}})
    assert r.status_code == 200 and r.get_json()['data']['margin']['gross'] == 8_000_000
    bad = app.test_client().post('/api/fuentes/costos', json={'lat': -28.5, 'lon': -59.0, 'params': {'heads': -5}})
    assert bad.status_code == 400


def test_costs_in_pdf_data():
    import report_typst as rt
    m = cs.margin(cs.clean(P), km=300)
    d = rt.build_data({'evidence': [], 'location': {'lat': -28.5, 'lon': -59.0}}, 'L',
                      {'costos': {'margin': m, 'logistics': {'km': 300, 'hours': 4.2, 'method': 'OSRM', 'destination': {'name': 'X'}}}})
    assert any(c['label'] == 'Distancia al destino' for c in d['costs'])
    assert d['costs_lines'][1]['value'].startswith('− $')
