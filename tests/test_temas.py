"""Temas v1: catálogo único de temas/variables que alimenta página, informe y newsletter,
cada uno declarando de dónde viene el dato y cómo se obtiene (procedencia). Red simulada."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import scales, temas


class R:
    def __init__(self, data=None, text=None, status=200):
        self._d, self.text, self.status_code = data, text if text is not None else json.dumps(data), status
        self.headers = {'Content-Type': 'application/json'}
        self.content = self.text.encode()
    @property
    def ok(self): return self.status_code < 400
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests; raise requests.HTTPError(str(self.status_code))


def fake_get(url, params=None, headers=None, timeout=None, **kw):
    if 'oni.ascii' in url:
        return R(text='SEAS YR TOTAL ANOM\nSON 2026 27.0 0.7\n', status=200)
    if 'RONI.ascii' in url:
        return R(text='SEAS YR ANOM\nSON 2026 0.6\n', status=200)
    if 'wksst9120' in url:
        return R(text=' 07OCT2026     20.9 0.4     25.9 1.6     28.6 2.1     29.6 1.0\n', status=200)
    if 'ensodisc' in url:
        return R(text='ENSO Alert System Status: El Niño Advisory', status=200)
    return R({}, status=404)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'get', fake_get)
    from api.index import app
    return app.test_client()


# ── catálogo ──
def test_catalog_has_topics_and_provenance():
    cat = temas.catalog()
    ids = {t['id'] for t in cat}
    assert {'nino', 'crecidas', 'inundaciones', 'poblaciones', 'evacuados'} <= ids
    for t in cat:
        assert {'id', 'title', 'group', 'organism', 'how', 'source_url', 'scale'} <= set(t)
        assert t['how'] and t['organism'] and t['source_url']
        assert 'resolver' not in t          # el resolver no se serializa


def test_ids_are_the_catalog_keys():
    assert temas.ids() == [t['id'] for t in temas.catalog()]


# ── resolución con procedencia ──
def test_resolve_unknown_topic():
    with pytest.raises(KeyError):
        temas.resolve('no-existe', -31, -60, {})


def test_resolve_evacuados_is_sin_dato():
    out = temas.resolve('evacuados', -31, -60, {})
    assert out['status'] == 'sin dato' and out['data'] is None
    assert out['organism'] and out['how']


def test_resolve_poblaciones_needs_locality():
    out = temas.resolve('poblaciones', -31, -60, {})
    assert out['status'] == 'sin dato'


def test_resolve_nino(monkeypatch):
    import enso_panel
    monkeypatch.setattr(enso_panel, 'enso_panel',
                        lambda: c.envelope({'phase': {'en': 'El Nino'}}, 'u', 's', 'NOAA CPC'))
    out = temas.resolve('nino', None, None, {})
    assert out['status'] == 'recibido' and out['data']['phase']['en'] == 'El Nino'
    assert out['id'] == 'nino' and out['title'] and out['how']
    assert out['requested_at']


# ── escalas nuevas viajan con el dato ──
def test_river_scales_present():
    assert 'caudal_percentil' in scales.ids() and 'rio_nivel_pct' in scales.ids()
    b = scales.band('caudal_percentil', 82)
    assert b['max'] == 100 and b['tone'] == 'risk'
    high = scales.band('rio_nivel_pct', 105)
    assert high['label'] == 'sobre el nivel de evacuación' and high['tone'] == 'risk'


# ── endpoints ──
def test_temas_endpoint(client):
    r = client.get('/api/fuentes/temas')
    assert r.status_code == 200
    j = r.get_json()
    assert 'nino' in j['ids'] and 'crecidas' in j['ids']
    assert all({'id', 'organism', 'how'} <= set(t) for t in j['temas'])


def test_tema_endpoint_unknown(client):
    r = client.get('/api/fuentes/tema/desconocido?lat=-31&lon=-60')
    assert r.status_code == 404


def test_tema_endpoint_evacuados(client):
    r = client.get('/api/fuentes/tema/evacuados?lat=-31&lon=-60')
    assert r.status_code == 200
    j = r.get_json()
    assert j['status'] == 'sin dato' and j['how']


def test_tema_endpoint_nino(client, monkeypatch):
    import enso_panel
    monkeypatch.setattr(enso_panel, 'enso_panel',
                        lambda: c.envelope({'phase': {'es': 'El Niño'}}, 'u', 's', 'NOAA CPC'))
    r = client.get('/api/fuentes/tema/nino?lat=-31&lon=-60')
    assert r.status_code == 200
    j = r.get_json()
    assert j['status'] == 'recibido' and j['data']['phase']['es'] == 'El Niño'


# ── alcance: punto, estación o zona delimitada ──
def test_catalog_declares_scope():
    scopes = {t['id']: t['scope'] for t in temas.catalog()}
    assert scopes['inundaciones'] == 'zona'
    assert scopes['crecidas'] == 'estación'
    assert scopes['nino'] == 'global'
    assert all(scopes[t['id']] for t in temas.catalog())


def test_nearest_station():
    assert temas.nearest_station(-28.5, -59.05) == 'parana-bellavista'


def test_zone_metadata_and_centroid():
    import informe_temas
    poly = [[-31.0, -60.0], [-31.1, -60.0], [-31.1, -60.1], [-31.0, -60.1]]
    doc = informe_temas.build(['evacuados'], None, None, {'poligono': poly}, 'Zona')
    assert doc['zone']['vertices'] == 4
    assert doc['zone']['centroid'] == [-31.05, -60.05]
    assert doc['point'] == [-31.05, -60.05]         # se toma el centroide de la zona


def test_crecidas_focus_by_locality(monkeypatch):
    import cuenca
    monkeypatch.setattr(cuenca, 'rivers', lambda: {'stations': [
        {'id': 'parana-goya', 'place': 'Goya', 'status': 'recibido'},
        {'id': 'parana-rosario', 'place': 'Rosario', 'status': 'recibido'}]})
    out = temas.resolve('crecidas', None, None, {'localidad': 'parana-goya'})
    assert out['data']['focus'] == 'parana-goya' and len(out['data']['stations']) == 1


def test_build_is_resilient_to_source_failure(monkeypatch):
    import informe_temas

    def boom(lat, lon, p):
        raise RuntimeError('caída')
    monkeypatch.setitem(temas.TEMAS['nino'], 'resolver', boom)
    doc = informe_temas.build(['nino'], -31, -60, {})
    b = doc['blocks'][0]
    assert b['status'] == 'sin dato' and 'no respondió' in b['error'].lower()


# ── informe y newsletter genéricos por tema ──
def test_summary_nino(monkeypatch):
    import enso_panel, informe_temas
    monkeypatch.setattr(enso_panel, 'enso_panel',
                        lambda: c.envelope({'phase': {'es': 'El Niño fuerte'}, 'oni': {'anom': 1.6}}, 'u', 's', 'NOAA CPC'))
    doc = informe_temas.build(['nino'], None, None, {})
    lines = informe_temas.summary(doc['blocks'][0])
    assert any('El Niño fuerte' in l for l in lines)
    assert any('ONI' in l for l in lines)


def test_informe_pdf_evacuados():
    import informe_temas
    doc = informe_temas.build(['evacuados', 'inundaciones'], -31, -60, {})
    out = informe_temas.pdf(doc)
    assert out[:5] == b'%PDF-' and len(out) > 2000


def test_newsletter_html_has_provenance():
    import informe_temas
    doc = informe_temas.build(['evacuados'], -31, -60, {})
    h = informe_temas.html(doc)
    assert 'Evacuados' in h and 'SINAGIR' in h and 'sin dato' in h


def test_newsletter_endpoint(client):
    r = client.get('/api/fuentes/newsletter-temas?temas=evacuados&lat=-31&lon=-60')
    assert r.status_code == 200 and 'text/html' in r.headers['Content-Type']
    assert 'Evacuados' in r.get_data(as_text=True)


def test_newsletter_endpoint_sin_coordenadas(client):
    r = client.get('/api/fuentes/newsletter-temas?temas=evacuados')
    assert r.status_code == 200 and 'text/html' in r.headers['Content-Type']


def test_informe_temas_endpoint(client):
    r = client.post('/api/fuentes/informe-temas', json={'temas': ['evacuados'], 'lat': -31, 'lon': -60})
    assert r.status_code == 200 and r.headers['Content-Type'] == 'application/pdf'
    assert r.get_data()[:5] == b'%PDF-'


# ── digest El Niño y crecidas (lo escribe la tarea cada 2 h) ──
def test_nino_crecidas_endpoint(client, monkeypatch):
    import datastore
    monkeypatch.setattr(datastore, 'load',
                        lambda *a, **k: {'updated': '2026-10-18T08:23', 'niveles': {'Alerta': 1}, 'enso': {'estado': 'El Niño'}})
    r = client.get('/api/fuentes/nino-crecidas')
    assert r.status_code == 200
    j = r.get_json()
    assert j['status'] == 'recibido'
    assert j['data']['niveles']['Alerta'] == 1 and j['data']['enso']['estado'] == 'El Niño'


def test_nino_crecidas_endpoint_sin_datos(client, monkeypatch):
    import datastore
    monkeypatch.setattr(datastore, 'load', lambda *a, **k: {})
    r = client.get('/api/fuentes/nino-crecidas')
    assert r.status_code == 200 and r.get_json()['data'] == {}
