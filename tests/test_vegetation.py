"""NDVI por lote con red simulada: Planetary Computer, Sentinel Hub, openEO y Earth Engine."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import vegetation as veg

LOT = [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]


class R:
    def __init__(self, data=None, status=200, ctype='application/json', content=None):
        self._d, self.status_code = data, status
        self.headers = {'Content-Type': ctype}
        self.content = content if content is not None else json.dumps(data).encode()
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests; raise requests.HTTPError(str(self.status_code))


def item(i, day, baseline='05.10', cloud=5):
    return {'id': f'S2B_MSIL2A_202610{day:02d}_{i}', 'properties': {
        'datetime': f'2026-10-{day:02d}T13:50:00Z', 'eo:cloud_cover': cloud, 's2:processing_baseline': baseline}}


def stats(mean, **kw):
    return {'type': 'Feature', 'properties': {'statistics': {'expr': dict(mean=mean, median=mean, std=0.05,
            percentile_2=mean - 0.2, percentile_98=mean + 0.1, valid_pixels=4400, **kw)}}}


CALLS = []


def pc_post(url, json=None, params=None, **kw):
    CALLS.append((url, params, json))
    if url.endswith('/search'):
        assert json['intersects']['type'] == 'Polygon'
        return R({'features': [item(1, 8), item(2, 3), item(3, 1, cloud=40)]})
    if url.endswith('/item/statistics'):
        if params['expression'].startswith('where('):
            # escena del día 1: lote cubierto
            return R(stats(0.2 if '20261001' in params['item'] else 0.95))
        return R(stats(0.71 if '20261008' in params['item'] else 0.64))
    if url.endswith('/item/feature.png'):
        return R(None, ctype='image/png', content=b'\x89PNG...')
    return R({}, status=404)


@pytest.fixture
def pc(monkeypatch):
    CALLS.clear()
    monkeypatch.setattr(c.SESSION, 'post', pc_post)


def test_geojson_closed_and_lonlat():
    g = veg.geojson_polygon(LOT)
    assert g['coordinates'][0][0] == [-59.05, -28.51] and g['coordinates'][0][0] == g['coordinates'][0][-1]


def test_area_hectares_reasonable():
    # 0.02° x 0.02° a -28.5° ≈ 1950 m x 2210 m ≈ 431 ha
    assert 400 < veg.area_ha(LOT) < 460


def test_polygon_required():
    with pytest.raises(ValueError):
        veg.ndvi_open(None)


def test_offset_by_processing_baseline():
    assert veg.ndvi_expression(item(1, 1, '05.10')) == '(B08-B04)/(B08+B04-2000)'
    assert veg.ndvi_expression(item(1, 1, '03.01')) == '(B08-B04)/(B08+B04)'


def test_ndvi_open_masks_cloudy_lot(pc):
    env = veg.ndvi_open(LOT)
    d = env['data']
    assert env['status'] == 'recibido' and d['capability'] == 'ANALYSIS'
    by = {r['datetime'][:10]: r for r in d['series']}
    assert by['2026-10-01']['status'] == 'nublada' and 'ndvi_mean' not in by['2026-10-01']
    assert by['2026-10-08']['ndvi_mean'] == 0.71 and d['latest']['datetime'].startswith('2026-10-08')
    assert d['valid_scenes'] == 2
    # la escena nublada no pide NDVI: 3 máscaras + 2 NDVI
    assert sum(1 for u, *_ in CALLS if u.endswith('/item/statistics')) == 5


def test_ndvi_png_validates_item(pc):
    with pytest.raises(ValueError):
        veg.ndvi_png('../../etc', LOT)
    png, bounds = veg.ndvi_png('S2B_MSIL2A_20261008_1', LOT, '05.10')
    assert png.startswith(b'\x89PNG') and bounds == [[-28.51, -59.05], [-28.49, -59.03]]


def test_sentinel_hub_requires_credential(monkeypatch):
    monkeypatch.delenv('CDSE_CLIENT_ID', raising=False)
    with pytest.raises(PermissionError):
        veg.sentinel_hub_ndvi(LOT)


def test_sentinel_hub_series(monkeypatch):
    monkeypatch.setenv('CDSE_CLIENT_ID', 'id'); monkeypatch.setenv('CDSE_CLIENT_SECRET', 's')
    veg._TOKEN.update(value=None, exp=0)
    def post(url, json=None, data=None, headers=None, **kw):
        if 'openid-connect/token' in url:
            return R({'access_token': 'T', 'expires_in': 600})
        assert headers['Authorization'] == 'Bearer T'
        def iv(day, mean, nod):
            return {'interval': {'from': f'2026-10-{day:02d}T00:00:00Z', 'to': f'2026-10-{day+5:02d}T00:00:00Z'},
                    'outputs': {'ndvi': {'bands': {'B0': {'stats': {'mean': mean, 'stDev': .04, 'sampleCount': 100,
                                                                 'noDataCount': nod, 'percentiles': {'50.0': mean}}}}}}}
        return R({'data': [iv(1, 0.5, 70), iv(6, 0.66, 5)]})
    monkeypatch.setattr(c.SESSION, 'post', post)
    d = veg.sentinel_hub_ndvi(LOT)['data']
    assert [r['status'] for r in d['series']] == ['nublada', 'válida'] and d['latest']['ndvi_mean'] == 0.66


def test_openeo_graph_and_parse(monkeypatch):
    monkeypatch.setenv('CDSE_CLIENT_ID', 'id'); monkeypatch.setenv('CDSE_CLIENT_SECRET', 's')
    veg._TOKEN.update(value='T', exp=9e12)
    g = veg.openeo_graph(LOT, '2026-06-01', '2026-10-01')['process_graph']
    assert g['save']['result'] and g['agg']['arguments']['geometries']['type'] == 'Polygon'
    def post(url, json=None, headers=None, **kw):
        assert headers['Authorization'] == 'Bearer oidc/CDSE/T'
        return R({'2026-10-03T00:00:00Z': [[0.62]], '2026-09-28T00:00:00Z': [[None]], '2026-09-20T00:00:00Z': [[0.58]]})
    monkeypatch.setattr(c.SESSION, 'post', post)
    d = veg.openeo_ndvi(LOT)['data']
    assert [r['ndvi_mean'] for r in d['series']] == [0.58, 0.62]


def test_gee_expression_shape():
    e = veg.gee_expression(LOT, 5)['expression']
    assert e['result'] == 'out'
    m = e['values']['out']['functionInvocationValue']
    assert m['functionName'] == 'Collection.map'
    assert m['arguments']['baseAlgorithm']['functionDefinitionValue']['body'] == 'body'
    json.dumps(e)  # serializable


def test_gee_requires_credential(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
    with pytest.raises(PermissionError):
        veg.gee_ndvi(LOT)


def test_routes(monkeypatch, pc):
    monkeypatch.delenv('CDSE_CLIENT_ID', raising=False)
    from api.index import app
    cl = app.test_client()
    q = '?lat=-28.5&lon=-59.04&polygon=' + json.dumps(LOT)
    r = cl.get('/api/fuentes/ndvi' + q)
    assert r.status_code == 200 and r.json['data']['valid_scenes'] == 2
    assert cl.get('/api/fuentes/ndvi?lat=-28.5&lon=-59.04').status_code == 400
    assert cl.get('/api/fuentes/sentinel-hub-ndvi' + q).status_code == 409
    img = cl.get('/api/fuentes/ndvi-imagen' + q + '&item=S2B_MSIL2A_20261008_1&baseline=05.10')
    assert img.status_code == 200 and img.mimetype == 'image/png'
    assert cl.get('/api/fuentes/ndvi' + q + '&days=9999').status_code == 400
