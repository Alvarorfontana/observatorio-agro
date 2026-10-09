"""Reglas de alertas con datos controlados."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
import alerts as al

ENS = {'days': [{'date': f'2026-10-{d:02d}', 'p_frost': 70 if d == 12 else 0, 'tmin_med': -1.5, 'p_heat35': 0,
                 'p_rain25': 50 if d == 14 else 0} for d in range(10, 25)]}


def test_frost_rule_levels():
    a, why = al.rule_frost(ENS)
    assert why is None and a[0]['level'] == 'alta' and '12/10' in a[0]['detail']
    assert al.rule_frost({'days': []}) == (None, 'sin pronóstico por conjunto')


def test_heat_rule_thi():
    hourly = {'time': [f'2026-10-10T{h:02d}:00' for h in range(24)], 'temperature_2m': [36] * 24, 'relative_humidity_2m': [60] * 24}
    a, _ = al.rule_heat(hourly, None)
    assert a[0]['level'] == 'alta' and 'THI' in a[0]['detail']
    cool = {'time': hourly['time'], 'temperature_2m': [20] * 24, 'relative_humidity_2m': [50] * 24}
    assert al.rule_heat(cool, None) == ([], None)


def test_rain_and_drought():
    a, _ = al.rule_rain(ENS, {'time': ['2026-10-10'], 'precipitation_sum': [5]})
    assert a[0]['key'] == 'lluvia' and a[0]['level'] == 'media'
    a, _ = al.rule_rain(None, {'time': ['2026-10-11'], 'precipitation_sum': [80]})
    assert a[0]['level'] == 'alta'
    d, _ = al.rule_drought({'spi': {'3': {'spi': -1.7, 'mm': 90, 'normal': 300, 'class': 'sequía severa'}}}, None)
    assert d[0]['level'] == 'alta' and 'SPI -1.7' in d[0]['detail']
    d, _ = al.rule_drought(None, {'precipitation_sum': [0] * 7, 'et0_fao_evapotranspiration': [6] * 7})
    assert d[0]['level'] == 'baja'


def test_fire_and_ndvi():
    assert al.rule_fire(None)[0] is None
    a, _ = al.rule_fire({'detections': [{'inside_lot': True, 'acq_date': '2026-10-09', 'acq_time': '0412', 'confidence': 'h'}]})
    assert a[0]['level'] == 'alta'
    a, _ = al.rule_ndvi({'series': [{'status': 'válida', 'ndvi_mean': 0.72, 'datetime': '2026-09-28'},
                                    {'status': 'nublada'}, {'status': 'válida', 'ndvi_mean': 0.55, 'datetime': '2026-10-08'}]})
    assert a[0]['key'] == 'vegetacion' and a[0]['level'] == 'media'
    assert al.rule_ndvi({'series': []})[0] is None


def test_evaluate_uses_known_and_reports_unevaluated(monkeypatch):
    monkeypatch.delenv('FIRMS_MAP_KEY', raising=False)
    def ext(url, params=None, **k):
        return c.envelope({'hourly': {'time': ['2026-10-10T15:00'], 'temperature_2m': [25], 'relative_humidity_2m': [50]},
                           'daily': {'time': ['2026-10-10'], 'precipitation_sum': [1], 'et0_fao_evapotranspiration': [4]}}, url, 's', 'o')
    monkeypatch.setattr(c, 'external', ext)
    env = al.evaluate(-28.5, -59.0, None, {'estadistica': {'ensemble': ENS}})
    d = env['data']
    assert env['status'] == 'recibido'
    assert {a['key'] for a in d['alerts']} >= {'helada', 'lluvia'}
    assert 'fuego' in d['unevaluated'] and 'vegetación' in d['unevaluated']
    assert d['alerts'][0]['level'] == 'alta'
