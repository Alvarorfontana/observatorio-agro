"""Estaciones de Brasil, Chile y Canadá: fuente nativa con clave o respaldo NOAA ISD, nunca otro país lejano."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
import stations as st

class R:
    def __init__(self, js=None): self._js = js
    def json(self): return self._js


METARS = [
    {'icaoId': 'SBUG', 'name': 'Uruguaiana/Rubem Berta Intl, RS, BR', 'lat': -29.78, 'lon': -57.04, 'obsTime': 2, 'reportTime': '2026-10-13T01:00:00Z',
     'temp': 25, 'dewp': 15, 'wspd': 9, 'altim': 1013, 'wxString': None},
    {'icaoId': 'SBUG', 'name': 'Uruguaiana/Rubem Berta Intl, RS, BR', 'lat': -29.78, 'lon': -57.04, 'obsTime': 1, 'temp': 20, 'dewp': 15},
    {'icaoId': 'SARP', 'name': 'Posadas, MI, AR', 'lat': -27.39, 'lon': -55.97, 'obsTime': 2, 'temp': 22},
]


def test_brasil_sin_clave_usa_metar_de_frontera(monkeypatch):
    monkeypatch.delenv('INMET_TOKEN', raising=False)
    seen = {}
    def get(url, params=None, headers=None, timeout=None):
        seen.update(params or {}); return R(METARS)
    monkeypatch.setattr(c, '_get', get)
    d = c.national('inmet', -28.55, -58.70)['data']       # lote en Corrientes
    assert d['source_mode'] == 'respaldo METAR' and 'INMET_TOKEN' in d['native_note']
    t = next(o for o in d['observations'] if o['variable'] == 'Temperatura')
    assert t['value'] == 25 and 'SBUG' in t['station'] and 200 < t['distance_km'] < 230   # el parte más nuevo
    assert next(o for o in d['observations'] if o['variable'] == 'Viento')['value'] == 16.7
    assert [x['id'] for x in d['stations']] == ['SBUG']        # el aeropuerto argentino no entra en "Brasil"
    assert seen['format'] == 'json'


def test_chile_lejos_no_inventa(monkeypatch):
    monkeypatch.setattr(c, '_get', lambda *a, **k: R([]))
    env = c.national('dmc', -28.55, -58.70)
    assert env['data']['observations'] == [] and 'fuera de Chile' in env['data']['scope']
    env = c.national('dmc', -31.0, -66.5)
    assert env['status'] == 'sin dato' and env['data']['observations'] == []


def test_canada_fuera_de_rango(monkeypatch):
    env = c.national('eccc', -28.55, -58.70)
    assert 'fuera de Canadá' in env['data']['scope'] and env['data']['observations'] == []


def test_eccc_parsea_swob(monkeypatch):
    js = {'features': [{'geometry': {'coordinates': [-75.7, 45.4]}, 'properties': {
        'stn_nam-value': 'OTTAWA CDA RCS', 'date_tm-value': '2026-10-12T20:00:00Z', 'air_temp': 12.3, 'rel_hum': 70, 'avg_wnd_spd_10m_pst10mts': 9.0}}]}
    monkeypatch.setattr(c, '_get', lambda *a, **k: R(js))
    env = c.national('eccc', 45.4, -75.69)
    assert env['data']['source_mode'] == 'nativa'
    assert {o['variable'] for o in env['data']['observations']} == {'Temperatura', 'Humedad', 'Viento'}


def test_dmc_con_clave(monkeypatch):
    monkeypatch.setenv('DMC_USUARIO', 'x@y.cl'); monkeypatch.setenv('DMC_TOKEN', 't')
    js = {'datosEstaciones': [{'estacion': {'nombreEstacion': 'Quinta Normal', 'latitud': -33.44, 'longitud': -70.68},
                               'datos': [{'momento': '2026-10-12 20:00:00', 'temperatura': '18.2 °C', 'humedadRelativa': '45 %'}]}]}
    seen = {}
    def get(url, params=None, headers=None, timeout=None):
        seen.update(params or {}); return R(js)
    monkeypatch.setattr(c, '_get', get)
    env = c.national('dmc', -33.45, -70.66)
    assert seen['usuario'] == 'x@y.cl' and env['data']['source_mode'] == 'nativa'
    assert env['data']['observations'][0]['value'] == 18.2
