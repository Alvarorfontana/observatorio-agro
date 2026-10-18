"""Competitivo v1: escalas con mínimo y máximo, ventana de pulverización, riesgo de enfermedad
por clima y asesor ampliado. Módulos puros y endpoints con red simulada."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import datetime, timedelta
import pytest
import research_connectors as c
import scales, spray_window, disease, vegetation


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


def _hours(n=168):
    start = datetime(2026, 10, 18, 0)
    time = [(start + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M') for i in range(n)]
    temp = [14 + (8 if 10 <= i % 24 <= 17 else 0) for i in range(n)]
    rh = [95 if i % 24 < 8 else 55 for i in range(n)]        # noche húmeda: mojado foliar
    wind = [6 if 8 <= i % 24 <= 18 else 2 for i in range(n)]  # día apto, noche calma (inversión)
    precip = [0.0] * n
    return {'time': time, 'temperature_2m': temp, 'relative_humidity_2m': rh, 'wind_speed_10m': wind, 'precipitation': precip}


def _layer(name, value, d_factor=1):
    return {'name': name, 'unit_measure': {'d_factor': d_factor, 'target_units': 'x'},
            'depths': [{'label': '0-5cm', 'values': {'mean': value}}]}


def fake_get(url, params=None, headers=None, timeout=None, **kw):
    if 'air-quality' in url:
        return R({'hourly': {'pm2_5': [35] * 24, 'pm10': [60] * 24, 'ozone': [120] * 24,
                             'nitrogen_dioxide': [30] * 24, 'carbon_monoxide': [200] * 24, 'sulphur_dioxide': [10] * 24}})
    if 'open-meteo.com/v1/forecast' in url:
        h = _hours()
        return R({'daily': {'time': sorted({t[:10] for t in h['time']}),
                            'et0_fao_evapotranspiration': [5.0] * 7, 'precipitation_sum': [0, 0, 10, 0, 0, 0, 0]},
                  'hourly': h})
    if 'soilgrids' in url:
        return R({'properties': {'layers': [_layer('wv0033', 3200, 100), _layer('wv1500', 1500, 100),
                                            _layer('soc', 150, 10), _layer('nitrogen', 15, 10)]}})
    if 'oni.ascii' in url:
        return R(text='SEAS YR TOTAL ANOM\nDJF 2026 26.1 0.2\nSON 2026 27.0 0.7\n', status=200)
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


# ── escalas: todo valor con mínimo y máximo ──
def test_scale_band_ndvi():
    b = scales.band('ndvi', 0.6)
    assert b['min'] == -1.0 and b['max'] == 1.0 and b['label'] == 'vigor alto' and b['tone'] == 'ok'
    assert b['position'] == 80
    assert scales.band('ndvi', None)['tone'] == 'idle' and scales.band('ndvi', None)['position'] is None
    assert scales.band('ndvi', 0.05)['label'] == 'suelo desnudo o muy bajo'


def test_scales_catalog_and_clamp():
    d = scales.describe('spray_index')
    assert d['min'] == 0 and d['max'] == 100 and len(d['bands']) == 3
    assert scales.clamp('spray_index', 150) == 100 and scales.clamp('spray_index', -5) == 0
    assert 'ndvi' in scales.ids() and all('bands' in s for s in scales.all_scales())


# ── ventana de pulverización ──
def test_wet_bulb_and_delta_t():
    assert 4 < spray_window.delta_t(20, 50) < 10
    assert spray_window.delta_t(15, 100) < 1.5          # saturación: casi sin depresión
    assert spray_window.scores(20, 60, 6, 0.0, 5)['rain'] == 100
    assert spray_window.scores(20, 60, 6, 3.0, 5)['rain'] == 0


def test_spray_window_evaluate():
    d = spray_window.evaluate(_hours(), 5)
    assert d['hours'] == 120 and all(0 <= r['index'] <= 100 for r in d['rows'])
    assert set(d['scales']) == {'wind_kph', 'delta_t', 'spray_index'}
    assert d['thresholds']['viento_kmh'] == [3.0, 11.0]
    night = [r for r in d['rows'] if int(r['time'][11:13]) < 8]
    assert night and all(r['index'] < 70 for r in night)   # noche: viento < 3 (inversión) limita
    assert isinstance(d['reading'], str)


def test_best_run_daylight():
    rows = [{'time': f'2026-10-18T{h:02d}:00', 'index': 80 if 10 <= h <= 14 else 30} for h in range(24)]
    best = spray_window.best_run(rows)
    assert best['hours'] == 5 and best['from'] == '10:00' and best['to'] == '14:00'
    assert spray_window.best_run([{'time': '2026-10-18T03:00', 'index': 90}]) is None   # fuera de franja diurna


# ── enfermedad por clima ──
def test_disease_favourability_and_evaluate():
    d = disease.DISEASES['trigo_septoria']
    assert disease.favourability(15, d) == 1.0
    assert disease.favourability(30, d) == 0.0
    out = disease.evaluate(_hours(), 'trigo_septoria', 7)
    assert out['risk_max'] >= 40 and out['scale']['max'] == 100
    assert out['temperature_range_c'] == [5, 22] and len(out['rows']) >= 1
    assert out['rows'][0]['band']['tone'] in ('ok', 'warn', 'risk')


def test_disease_unknown():
    with pytest.raises(ValueError):
        disease.evaluate(_hours(), 'no_existe')


# ── NDVI con escala y resumen zonal ──
def test_vegetation_classify_and_stats():
    assert vegetation.classify(0.75)['label'] == 'vigor muy alto'
    s = vegetation.window_stats([
        {'status': 'válida', 'ndvi_mean': 0.6, 'ndvi_p2': 0.4, 'ndvi_p98': 0.7, 'datetime': '2026-10-01T00:00:00Z'},
        {'status': 'válida', 'ndvi_mean': 0.5, 'ndvi_p2': 0.3, 'ndvi_p98': 0.6, 'datetime': '2026-10-09T00:00:00Z'},
        {'status': 'nublada', 'ndvi_mean': None, 'datetime': '2026-10-05T00:00:00Z'}])
    assert s['scenes'] == 2 and s['min_ndvi'] == 0.3 and s['max_ndvi'] == 0.7
    assert s['latest_ndvi'] == 0.5 and s['trend_ndvi'] == -0.1
    assert vegetation.window_stats([]) is None


# ── endpoints ──
def test_spray_endpoint(client):
    r = client.post('/api/fuentes/ventana-pulverizacion', json={'lat': -28.5, 'lon': -59.0, 'days': 3})
    assert r.status_code == 200 and r.get_json()['status'] == 'recibido'
    assert r.get_json()['data']['scales']['spray_index']['max'] == 100
    assert client.post('/api/fuentes/ventana-pulverizacion', json={'lat': -28.5, 'lon': -59.0, 'days': 99}).status_code == 400


def test_disease_endpoint(client):
    r = client.post('/api/fuentes/enfermedades', json={'lat': -28.5, 'lon': -59.0, 'crop': 'trigo'})
    assert r.status_code == 200
    d = r.get_json()['data']
    assert d['name'].startswith('Roya de la hoja') and d['scale']['max'] == 100


def test_scales_endpoint(client):
    r = client.get('/api/fuentes/escalas')
    assert r.status_code == 200
    ids = {s['scale'] for s in r.get_json()['scales']}
    assert {'ndvi', 'spray_index', 'disease_risk', 'spi', 'eaqi'} <= ids
    assert len(r.get_json()['enfermedades']) == len(disease.DISEASES)


def test_advisor_includes_spray_and_disease(client):
    r = client.post('/api/fuentes/asesor', json={'lat': -28.507, 'lon': -59.043, 'crop': 'trigo',
                                                 'sowing': '2026-08-01', 'yield_t_ha': 5})
    assert r.status_code == 200
    d = r.get_json()['data']
    assert d['pulverizacion'] and d['pulverizacion']['rows']
    assert d['enfermedad'] and d['enfermedad']['name'].startswith('Roya')
    assert d['aire']['scale']['min'] == 0 and d['aire']['scale']['max'] == 500


# ── informe: el asesor llega al PDF con su escala ──
ASESOR = {'status': 'recibido', 'data': {
    'agua': {'net_irrigation_mm': 24.5, 'etc_total_mm': 38.0, 'rain_total_mm': 13.5, 'gross_irrigation_mm': 32.7,
             'taw_mm': 170, 'raw_mm': 94, 'reading': 'Para trigo la ventana pide 38 mm de ETc.',
             'days': [{'rain_mm': 0, 'etc_mm': 5.0}, {'rain_mm': 10, 'etc_mm': 5.5}, {'rain_mm': 0, 'etc_mm': 6.0}]},
    'nitrogeno': {'demand_kg_ha': 135, 'supply_from_soil_kg_ha': 103, 'prev_crop_credit_kg_ha': 0,
                  'urea_kg_ha': 127, 'dose_kg_ha': 58, 'reading': 'trigo: demanda 135 kg N/ha.'},
    'aire': {'index': 68, 'category': 'mala', 'reading': 'Índice europeo 68 (mala).',
             'per_pollutant': {'ozone': {'label': 'O₃', 'value': 120, 'sub_index': 60}},
             'scale': {'min': 0, 'max': 500, 'label': 'mala', 'tone': 'risk'}},
    'pulverizacion': {'hours': 120, 'reading': 'Mejor ventana en 5 hora(s) el 2026-10-19 de 10:00 a 14:00 (aptitud 95/100).',
                      'best': {'date': '2026-10-19', 'from': '10:00', 'to': '14:00', 'hours': 5, 'index': 95},
                      'rows': [{'index': 95}, {'index': 80}, {'index': 20}]},
    'enfermedad': {'name': 'Roya de la hoja (trigo)', 'risk_max': 72, 'risk_max_date': '2026-10-20',
                   'wet_hours_required': 4, 'temperature_range_c': [10, 25],
                   'reading': 'Roya de la hoja (trigo): riesgo alto el 2026-10-20.',
                   'rows': [{'date': '2026-10-18', 'risk': 40, 'wet_hours_in_range': 4, 'band': {'label': 'alto', 'tone': 'risk'}},
                            {'date': '2026-10-19', 'risk': 55, 'wet_hours_in_range': 5, 'band': {'label': 'alto', 'tone': 'risk'}},
                            {'date': '2026-10-20', 'risk': 72, 'wet_hours_in_range': 6, 'band': {'label': 'muy alto', 'tone': 'risk'}}]},
    'lectura': 'Resumen del asesor con agua, nitrógeno, aire, pulverización y enfermedad.'}}


def test_report_includes_advisor_and_summary():
    pytest.importorskip('typst')
    import report_typst as rt
    lot = {'name': 'Lote Piloto', 'vertices': [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]}
    res = {'point': [-28.5, -59.0], 'generated_at': '2026-10-18T12:00:00Z', 'summary': '',
           'recommendations': ['Regar en la franja pronosticada'], 'findings': [], 'metrics': [],
           'confidence': {}, 'evidence': []}
    extras = {'lot': lot, 'asesor': ASESOR}
    d = rt.build_data(res, 'Lote Piloto', extras)
    assert len(d['advisor']['cards']) == 5 and len(d['advisor']['charts']) == 2
    assert 'Regar' in d['exec_summary']
    pdf, engine = rt.pdf(res, 'Lote Piloto', extras)
    assert engine == 'typst' and pdf[:5] == b'%PDF-'


# ── elegir los temas del informe (secciones) ──
def test_secciones_catalog_endpoint(client):
    r = client.get('/api/fuentes/informe/secciones')
    assert r.status_code == 200
    j = r.get_json()
    assert 'asesor' in j['ids'] and 'clima' in j['ids']
    assert len(j['ids']) == len(j['sections']) >= 18
    assert all({'id', 'title', 'group', 'desc'} <= set(s) for s in j['sections'])


def test_extras_merges_secciones():
    import research_routes as rr
    assert rr._extras({'extras': {'lot': {}}, 'secciones': ['clima']})['secciones'] == ['clima']
    assert rr._extras({'temas': ['asesor']})['secciones'] == ['asesor']
    assert 'secciones' not in rr._extras({'extras': {'lot': {}}})


def test_build_data_selected_and_filter():
    import report_typst as rt
    res = {'point': [-28.5, -59.0], 'confidence': {}, 'evidence': []}
    d = rt.build_data(res, 'L', {'secciones': ['asesor', 'clima', 'no-existe']})
    assert d['selected'] == ['asesor', 'clima']
    assert rt.section_ids() == [s['id'] for s in d['sections']]
    assert rt.build_data(res, 'L', {})['selected'] is None
    assert rt.build_data(res, 'L', {'temas': []})['selected'] is None


def test_report_respects_selected_sections():
    pytest.importorskip('typst')
    import report_typst as rt
    lot = {'name': 'Lote Piloto', 'vertices': [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]}
    res = {'point': [-28.5, -59.0], 'generated_at': '2026-10-18T12:00:00Z', 'summary': '',
           'recommendations': [], 'findings': [], 'metrics': [], 'confidence': {}, 'evidence': []}
    extras = {'lot': lot, 'asesor': ASESOR, 'secciones': ['resumen', 'asesor']}
    d = rt.build_data(res, 'Lote Piloto', extras)
    assert d['selected'] == ['resumen', 'asesor']
    pdf, engine = rt.pdf(res, 'Lote Piloto', extras)
    assert engine == 'typst' and pdf[:5] == b'%PDF-'


