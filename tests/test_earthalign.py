"""Pruebas de earthalign: contrato del envelope, elección del recorte más cercano y ruta (sin torch ni red)."""
import json, os, sys
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


def test_date_admite_dict_o_texto():
    assert build._date({'year': 2007, 'month': 3, 'day': 4, 'time': '09:00'}) == '2007-03-04'
    assert build._date('2015-07-01 12:00') == '2015-07-01'
    assert build._date(None) == ''


def test_latlon_desde_metadata_o_bbox():
    assert build._latlon({'METADATA': {'lat': -20.31, 'lon': 118.57}}) == (-20.31, 118.57)
    assert build._latlon({'METADATA': {'bbox_lat_lon': '[-24.2, -20, 116, 120]'}}) == (-22.1, 118.0)
    assert build._latlon({'METADATA': {}}) is None
    assert build._latlon({}) is None


def test_captions_normaliza_varios_formatos():
    assert build._captions({'physical_framing': 'x'}) == {'physical_framing': 'x'}
    assert build._captions(['a', 'b']) == {eal.CAPTION_STYLES[0]: 'a', eal.CAPTION_STYLES[1]: 'b'}
    assert build._captions([{'style': 'impact_focused', 'caption': 'c'}]) == {'impact_focused': 'c'}
    assert build._captions(None) == {}


def test_trae_las_descripciones_en_espanol(monkeypatch):
    doc = _doc()
    doc['samples'][0]['captions_es'] = {'natural_event_focused': 'Una ola de frío en español.'}
    monkeypatch.setattr(eal.datastore, 'load', lambda *a, **k: doc)
    env = eal.describe(-33.0, -60.0)
    assert env['data']['captions_es']['natural_event_focused'].startswith('Una ola')
    assert env['data']['reading'].startswith('Una ola')      # resumen en español listo para mostrar


def test_traduccion_offline_es_opcional(monkeypatch):
    monkeypatch.setattr(build, '_argos', lambda: (_ for _ in ()).throw(RuntimeError('sin argos')))
    assert build.translate_es(['Hello']) is None             # sin Argos, no rompe: devuelve None
    assert build.translate_es([]) == []


def test_memoria_de_traduccion(tmp_path):
    p = tmp_path / 'earthalign.json'
    p.write_text(json.dumps({'samples': [{'captions': {'a': 'Hi'}, 'captions_es': {'a': 'Hola'}}]}), encoding='utf-8')
    assert build._load_cache(str(p)) == {'Hi': 'Hola'}
    assert build._load_cache(str(tmp_path / 'no-existe.json')) == {}


def test_extract_filtra_por_region():
    records = [
        {'METADATA': {'lat': -34.0, 'lon': -59.0}, 'ERA5_SNAPSHOT_TIME': {'year': 2015, 'month': 7, 'day': 1},
         'EVENT_CATEGORIES': 'Cold wave', 'CAPTIONS': {'physical_framing': 'frío'}},           # en la región
        {'METADATA': {'lat': 41.0, 'lon': 11.0}, 'ERA5_SNAPSHOT_TIME': '2015-07-01',
         'CAPTIONS': {'physical_framing': 'lejos'}},                                           # Europa: se descarta
        {'ERA5_SNAPSHOT_TIME': '2015-07-01', 'CAPTIONS': {'physical_framing': 'sin posición'}},  # sin posición: se descarta
        {'METADATA': {'lat': -34.0, 'lon': -59.0}, 'CAPTIONS': {}},                             # sin caption: se descarta
    ]
    got = build.extract(records)
    assert len(got) == 1
    assert got[0]['lat'] == -34.0 and got[0]['time'] == '2015-07-01'
    assert got[0]['event'] == 'Cold wave'
    assert got[0]['captions'] == {'physical_framing': 'frío'}

