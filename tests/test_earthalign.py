"""Pruebas de earthalign: contrato del envelope, elección del recorte más cercano y ruta (sin torch ni red)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import earthalign as eal
import earthalign_build as build


def _doc():
    return {
        'generated_at': '2026-10-16T00:00:00Z',
        'source': eal.CODE,
        'samples': [
            {'lat': -33.0, 'lon': -60.0, 'time': '2026-08-01',
             'event': 'ola de frío', 'classification': ['cold_wave'],
             'captions': {'natural_event_focused': 'Una ola de frío...'}},
            {'lat': -28.5, 'lon': -59.0, 'time': '2026-10-01',
             'event': None, 'classification': ['normal'],
             'captions': {'physical_framing': 'Campo de presión normal...'}},
        ],
    }


def test_sin_dato_si_no_hay_calculo(monkeypatch):
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: None)
    env = eal.describe(-28.5, -59.0)
    assert env['status'] == 'sin dato'
    assert env['data'] is None
    assert 'no fue calculada' in env['error']


def test_elige_el_recorte_mas_cercano(monkeypatch):
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: _doc())
    env = eal.describe(-28.51, -59.04)
    assert env['status'] == 'recibido'
    assert env['data']['event'] is None               # el de Corrientes, no el de Buenos Aires
    assert env['data']['distance_km'] < 10


def test_fuera_de_alcance_da_sin_dato(monkeypatch):
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: _doc())
    env = eal.describe(40.0, 10.0)                    # muy lejos de todo recorte
    assert env['status'] == 'sin dato'
    assert 'km' in env['error']


def test_la_fecha_desempata(monkeypatch):
    doc = _doc()
    doc['samples'] = [
        {'lat': -34.6, 'lon': -58.4, 'time': '2026-07-15', 'event': 'ola de frío', 'captions': {}},
        {'lat': -34.6, 'lon': -58.4, 'time': '2026-01-15', 'event': 'ola de calor', 'captions': {}},
    ]
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: doc)
    env = eal.describe(-34.6, -58.4, '2026-07-20')
    assert env['data']['event'] == 'ola de frío'


def test_status_refleja_lo_pendiente(monkeypatch):
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: None)
    s = eal.status()
    assert s['ready'] is False and s['samples'] == 0
    assert s['pending'] and s['weights'].startswith('https://')


def test_rutas_earthalign(monkeypatch):
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: _doc())
    from api.index import app
    client = app.test_client()
    r = client.get('/api/fuentes/earthalign?lat=-28.51&lon=-59.04')
    assert r.status_code == 200
    assert r.json['data']['event'] is None
    e = client.get('/api/fuentes/earthalign/estado')
    assert e.status_code == 200 and 'pending' in e.json
    assert client.get('/api/fuentes/earthalign?lat=x&lon=y').status_code == 400


def test_bbox_center():
    assert build.bbox_center([-60.0, -35.0, -58.0, -33.0]) == (-34.0, -59.0)
    assert build.bbox_center(None) is None
    assert build.bbox_center([1, 2]) is None


def test_captions_normaliza_varios_formatos():
    assert build._captions({'physical_framing': 'x'}) == {'physical_framing': 'x'}
    assert build._captions(['a', 'b']) == {eal.CAPTION_STYLES[0]: 'a', eal.CAPTION_STYLES[1]: 'b'}
    assert build._captions([{'style': 'impact_focused', 'caption': 'c'}]) == {'impact_focused': 'c'}
    assert build._captions(None) == {}


def test_extract_filtra_por_region():
    records = [
        {'ERA5_SNAPSHOT_BBOX': [-60.0, -35.0, -58.0, -33.0], 'ERA5_SNAPSHOT_TIME': '2015-07-01 12:00',
         'EVENT_CATEGORIES': ['cold wave'], 'CAPTIONS': {'physical_framing': 'frío'}},      # en la región
        {'ERA5_SNAPSHOT_BBOX': [10.0, 40.0, 12.0, 42.0], 'ERA5_SNAPSHOT_TIME': '2015-07-01',
         'CAPTIONS': {'physical_framing': 'lejos'}},                                        # Europa: se descarta
        {'ERA5_SNAPSHOT_TIME': '2015-07-01', 'CAPTIONS': {'physical_framing': 'sin bbox'}}, # sin bbox: se descarta
        {'ERA5_SNAPSHOT_BBOX': [-60.0, -35.0, -58.0, -33.0], 'CAPTIONS': {}},               # sin caption: se descarta
    ]
    got = build.extract(records)
    assert len(got) == 1
    assert got[0]['lat'] == -34.0 and got[0]['time'] == '2015-07-01'
    assert got[0]['captions'] == {'physical_framing': 'frío'}

