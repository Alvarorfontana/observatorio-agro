"""Estaciones de Brasil, Chile y Canadá: fuente nativa con clave o respaldo NOAA ISD, nunca otro país lejano."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
import stations as st

HIST = ('"USAF","WBAN","STATION NAME","CTRY","STATE","ICAO","LAT","LON","ELEV(M)","BEGIN","END"\n'
        '"839280","99999","URUGUAIANA","BR","","SBUG","-29.783","-57.033","+0074.0","19730101","20991231"\n'
        '"837000","99999","VIEJA","BR","","","-29.0","-57.5","+0074.0","19730101","20000101"\n'
        '"855740","99999","SANTIAGO","CI","","SCEL","-33.383","-70.783","+0474.0","19730101","20991231"\n')


class R:
    def __init__(self, js=None, text='', content=b'x'): self._js, self.text, self.content = js, text, content
    def json(self): return self._js


def fake(monkeypatch, rows):
    st._ISD.update(t=0, rows=[])
    def get(url, params=None, headers=None, timeout=None):
        if url == st.ISD_HISTORY: return R(text=HIST)
        if url == st.ISD_DATA: return R(rows)
        raise ConnectionError(url)
    monkeypatch.setattr(c, '_get', get)


def test_brasil_sin_clave_usa_noaa_con_estacion_de_frontera(monkeypatch):
    monkeypatch.delenv('INMET_TOKEN', raising=False)
    fake(monkeypatch, [{'STATION': '83928099999', 'DATE': '2026-10-11T12:00:00', 'TMP': '+0251,1', 'DEW': '+0150,1', 'SLP': '10132,1', 'WND': '160,1,N,0046,1'}])
    env = c.national('inmet', -28.55, -58.70)       # lote en Corrientes
    d = env['data']
    assert d['source_mode'] == 'respaldo NOAA' and 'INMET_TOKEN' in d['native_note']
    t = next(o for o in d['observations'] if o['variable'] == 'Temperatura')
    assert t['value'] == 25.1 and t['station'] == 'Uruguaiana' and 200 < t['distance_km'] < 230
    assert next(o for o in d['observations'] if o['variable'] == 'Viento')['value'] == 16.6
    assert [s['name'] for s in d['stations']] == ['Uruguaiana']        # la estación cerrada no aparece


def test_chile_lejos_no_inventa(monkeypatch):
    fake(monkeypatch, [])
    env = c.national('dmc', -28.55, -58.70)          # Corrientes está lejos de Chile: no se muestran estaciones chilenas
    assert env['data']['observations'] == [] and 'fuera de Chile' in env['data']['scope']
    env = c.national('dmc', -31.0, -66.5)            # La Rioja: dentro del alcance, pero Santiago queda a >300 km
    assert env['status'] == 'sin dato' and env['data']['observations'] == []


def test_canada_fuera_de_rango(monkeypatch):
    env = c.national('eccc', -28.55, -58.70)
    assert 'fuera de Canadá' in env['data']['scope'] and env['data']['observations'] == []


def test_isd_descarta_datos_faltantes():
    assert st._isd_val('+9999,9') is None and st._isd_val('+0251,3') is None and st._isd_val('-0035,1') == -3.5


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
