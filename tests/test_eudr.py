"""Informe de libre de deforestación y GeoJSON EUDR."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import report_typst as rt

LOT = {'name': 'Potrero Norte', 'vertices': [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]], 'areaHa': 431.2, 'perimeterKm': 8.4}
SUST = {'deforestation': {'verdict': 'sin pérdida de cobertura arbórea detectada', 'baseline_year': 2020, 'last_year': 2023, 'tree_loss_ha': 0.4,
                          'tree_change_pp': -0.1, 'series': [{'year': y, 'trees': .1, 'rangeland': .8, 'crops': .05, 'water': .01} for y in range(2017, 2024)]},
        'carbon': {'soc_t_ha': 48.0, 'soc_t_ha_range': [30, 70], 'soc_total_t': 20700, 'soc_total_tco2e': 75900}}


def test_geojson_six_decimals_and_closed():
    gj = rt.geojson_lot(LOT['vertices'], 'X', 431.2)
    poly, pt = gj['features']
    ring = poly['geometry']['coordinates'][0]
    assert ring[0] == ring[-1] and ring[0] == [-59.05, -28.51]
    assert pt['geometry']['type'] == 'Point' and poly['properties']['crs'] == 'EPSG:4326'


def test_eudr_data():
    d = rt.eudr_data(LOT, 'San Ramón', SUST)
    assert d['verdict']['tone'] == 'ok' and d['series'][3]['cut'] and len(d['geo_hash']) == 64
    assert any('-28.510000' in x for x in d['coords'])
    with pytest.raises(ValueError):
        rt.eudr_data({'vertices': []}, '', SUST)


def test_eudr_pdf_route():
    pytest.importorskip('typst')
    from api.index import app
    cl = app.test_client()
    r = cl.post('/api/fuentes/eudr/pdf', json={'lot': LOT, 'establecimiento': 'San Ramón', 'sustentabilidad': SUST})
    assert r.status_code == 200 and r.data[:5] == b'%PDF-' and len(r.headers['X-DOTS-GeoJSON-SHA256']) == 64
    g = cl.post('/api/fuentes/eudr/geojson', json={'lot': LOT})
    assert g.status_code == 200 and json.loads(g.data)['type'] == 'FeatureCollection'
    assert cl.post('/api/fuentes/eudr/geojson', json={'lot': {'vertices': [[1, 2]]}}).status_code == 400
