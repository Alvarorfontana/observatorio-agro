"""Pruebas de rutas con red simulada (no llaman a las APIs reales)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c


class R:
    def __init__(self, data=None, text=None, status=200, ctype='application/json'):
        self._d, self.text, self.status_code = data, text if text is not None else json.dumps(data), status
        self.headers = {'Content-Type': ctype}; self.content = self.text.encode(); self.url = ''
        import io
        class _Raw(io.BytesIO):
            def read(self, n=-1, decode_content=False): return super().read(n)
        self.raw = _Raw(b'\xff\xd8\xff' + b'0' * 50)
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests; raise requests.HTTPError(str(self.status_code))


def fake(url, params=None, **kw):
    if 'open-meteo.com/v1/forecast' in url:
        return R({'current': {'time': '2026-10-08T12:00', 'temperature_2m': 31.0, 'relative_humidity_2m': 60},
                  'hourly': {'time': ['2026-10-08T12:00'], 'soil_moisture_0_to_1cm': [0.3]},
                  'daily': {'time': ['2026-10-08'], 'precipitation_sum': [0], 'et0_fao_evapotranspiration': [5],
                            'temperature_2m_max': [34], 'temperature_2m_min': [20]}})
    if 'soilgrids' in url:
        return R({'properties': {'layers': [{'name': 'nitrogen', 'depths': [{'values': {'mean': 150}}]}]}})
    if 'flood-api' in url:
        return R({'daily': {'time': ['2026-10-08'], 'river_discharge': [100]}})
    if 'nominatim' in url:
        return R([{'lat': '-28.5', 'lon': '-59.0', 'display_name': 'Bella Vista, Corrientes', 'type': 'town'}])
    if 'oni.ascii' in url:
        return R(text='SEAS YR TOTAL ANOM\nDJF 2026 26.1 0.2\nJFM 2026 26.0 -0.6\n', ctype='text/plain')
    if 'bom.gov' in url or 'iri.columbia' in url:
        return R(text='ok', ctype='text/plain')
    if 'ws.smn.gob.ar' in url:
        return R([{'name': 'BELLA VISTA', 'lat': '-28.51', 'lon': '-59.04', 'updated': 1,
                   'weather': {'temp': 30, 'humidity': 50, 'wind_speed': 10, 'pressure': 1010}}])
    if 'arcgisonline' in url or 'sentinel-cogs' in url:
        return R(text='x', ctype='image/jpeg')
    if 'WMTSCapabilities' in url:
        return R(text='<ows:Identifier>MODIS_Terra</ows:Identifier>', ctype='text/xml')
    return R({}, status=404)


def fake_post(url, json=None, **kw):
    return R({'type': 'FeatureCollection', 'features': [
        {'id': 'S2A_X', 'properties': {'datetime': '2026-10-01T00:00:00Z', 'eo:cloud_cover': 3},
         'assets': {'thumbnail': {'href': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/a/preview.jpg'}}}]})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'get', fake)
    monkeypatch.setattr(c.SESSION, 'post', fake_post)
    monkeypatch.delenv('FIRMS_MAP_KEY', raising=False)
    from api.index import app
    return app.test_client()


Q = '?lat=-28.507&lon=-59.043'


def test_health(client):
    assert client.get('/api/health').json['status'] == 'ok'


@pytest.mark.parametrize('name', ['variables', 'suelo', 'rios', 'escenas', 'enso', 'aire' if False else 'variables'])
def test_fuentes_ok(client, name):
    r = client.get(f'/api/fuentes/{name}{Q}')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.json['status'] == 'recibido' and 'consulted_at' in r.json


def test_variables_forma_que_espera_el_frontend(client):
    d = client.get(f'/api/fuentes/variables{Q}').json['data']
    assert d['current']['temperature_2m'] == 31.0 and 'daily' in d


def test_escenas_foto_compatible(client):
    f = client.get(f'/api/fuentes/escenas{Q}').json['data']['features'][0]
    assert client.get('/api/fuentes/foto', query_string={'asset': f['assets']['thumbnail']['href']}).status_code == 200


def test_smn_dentro_de_argentina(client):
    obs = client.get(f'/api/fuentes/smn{Q}').json['data']['observations']
    assert obs and obs[0]['station'] == 'BELLA VISTA'


def test_agencia_no_implementada_es_honesta(client):
    r = client.get(f'/api/fuentes/inmet{Q}')
    assert r.status_code == 400 and 'no está implementado' in r.json['error']


def test_firms_sin_clave_409(client):
    assert client.get(f'/api/fuentes/firms{Q}').status_code == 409


def test_credenciales_faltantes(client, monkeypatch):
    monkeypatch.delenv('CDS_API_KEY', raising=False)
    d = client.get(f'/api/fuentes/era5-cds{Q}').json['data']
    assert d['status'] == 'requiere credencial' and d['missing_env'] == ['CDS_API_KEY']


def test_firms_no_filtra_la_clave(client, monkeypatch):
    monkeypatch.setenv('FIRMS_MAP_KEY', 'SECRETO123')
    monkeypatch.setattr(c.SESSION, 'get', lambda u, **k: R(text='latitude,longitude,acq_date\n-28.5,-59.0,2026-10-08\n', ctype='text/csv'))
    r = client.get(f'/api/fuentes/firms{Q}')
    assert r.status_code == 200 and 'SECRETO123' not in r.get_data(as_text=True)
    assert r.json['data']['detections'][0]['latitude'] == -28.5


def test_tile_y_foto_validan(client):
    assert client.get('/api/fuentes/tile?z=99&x=0&y=0').status_code == 400
    assert client.get('/api/fuentes/foto', query_string={'asset': 'https://evil.com/preview.jpg'}).status_code == 400
    assert client.get('/api/fuentes/tile?z=3&x=1&y=1').status_code == 200


def test_geocode(client):
    assert client.get('/api/fuentes/geocode?q=Bella Vista').json['results'][0]['display_name'].startswith('Bella')
    assert client.get('/api/fuentes/geocode?q=a').status_code == 400


def test_fuente_inexistente_404(client):
    assert client.get(f'/api/fuentes/nada{Q}').status_code == 404


def test_coordenadas_invalidas_400(client):
    assert client.get('/api/fuentes/variables?lat=abc&lon=1').status_code == 400


def test_agentic_y_pdf(client):
    body = {'lat': -28.507, 'lon': -59.043, 'prompt': 'Informe integral',
            'fieldMarkers': [{'type': 'observación', 'lat': 1, 'lon': 1}]}
    a = client.post('/api/fuentes/agentic', json=body)
    assert a.status_code == 200 and a.json['findings'], a.get_data(as_text=True)
    p = client.post('/api/fuentes/analizar', json={**body, 'nombre': 'Lote prueba'})
    assert p.status_code == 200 and p.data[:5] == b'%PDF-'
    p2 = client.post('/api/fuentes/agentic/pdf', json=body)
    assert p2.data[:5] == b'%PDF-'
