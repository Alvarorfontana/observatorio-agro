"""INA A5: niveles y caudales observados por polígono, resumen/tendencia y ruta (red simulada)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import ina_a5

LOT = [[-28.56, -58.71], [-28.56, -58.69], [-28.54, -58.69], [-28.54, -58.71]]


class R:
    def __init__(self, data=None, status=200):
        self._d, self.status_code = data, status
        self.headers = {'Content-Type': 'application/json'}
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests; raise requests.HTTPError(str(self.status_code))


def _serie(sid, est_id, var_id, codigo, nombre, lon, lat, alert=None, evac=None):
    return {'id': sid,
            'estacion': {'id': est_id, 'nombre': nombre, 'rio': 'PARANA', 'localidad': 'Corrientes',
                         'geom': {'type': 'Point', 'coordinates': [lon, lat]},
                         'nivel_alerta': alert, 'nivel_evacuacion': evac},
            'var': {'id': var_id, 'var': codigo, 'nombre': 'Altura hidrométrica' if var_id == 2 else 'Caudal'},
            'procedimiento': {'abrev': 'medicion'}, 'unidades': {'abrev': 'm' if var_id == 2 else 'm3/s'},
            'date_range': {'timeend': '2026-10-15T12:00:00', 'count': 100}}


def fake_get(url, params=None, headers=None, timeout=None):
    params = params or {}
    if url.endswith('/obs/puntual/series'):
        if params.get('var_id') == 2:
            return R({'rows': [_serie(101, 1, 2, 'H', 'Corrientes', -58.70, -28.55, alert=6.0, evac=7.0),
                               _serie(102, 2, 2, 'H', 'Bella Vista', -58.90, -28.60)]})
        return R({'rows': [_serie(201, 1, 4, 'Q', 'Corrientes', -58.70, -28.55)]})
    if '/obs/puntual/series/' in url:
        sid = int(url.rsplit('/', 1)[-1])
        base = 3.0 if sid == 101 else 1.0
        obs = [{'series_id': sid, 'timestart': f'2026-10-{d:02d}T12:00:00.000Z', 'valor': base + d * 0.1}
               for d in range(1, 6)]
        return R({'observaciones': obs})
    return R({}, 404)


@pytest.fixture
def ina(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'get', fake_get)


def test_local_y_resumen():
    assert ina_a5._local('2026-06-01T07:00:00.000Z') == '2026-06-01 04:00'   # UTC-3
    assert ina_a5._local(None) is None
    s = ina_a5._summary([{'datetime': 'a', 'valor': 1.0}, {'datetime': 'b', 'valor': 1.1}, {'datetime': 'c', 'valor': 1.2}],
                        alert=1.15)
    assert s['last_value'] == 1.2 and s['min'] == 1.0 and s['max'] == 1.2
    assert s['trend'] == 'subiendo' and s['level_state'] == 'nivel de alerta'


def test_pick_prefiere_medicion():
    a = _serie(1, 9, 2, 'H', 'X', -58, -28); a['procedimiento'] = {'abrev': 'otro'}
    b = _serie(2, 9, 2, 'H', 'X', -58, -28); b['date_range']['count'] = 5
    assert ina_a5._pick([a, b])[0]['id'] == 2


def test_analyze_referencia_y_serie(ina):
    env = ina_a5.analyze(LOT)
    assert env['status'] == 'recibido'
    d = env['data']
    assert d['reference']['station'] == 'Corrientes'          # más cercana al centro del lote
    assert d['reference']['last_value'] == 3.5 and d['reference']['alert_level'] == 6.0
    assert len(d['series']) == 5 and d['series'][-1]['valor'] == 3.5
    assert len(d['stations']) == 3 and d['stations'][0]['variable'] == 'Altura hidrométrica'


def test_sin_estaciones_da_sin_dato(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'get', lambda *a, **k: R({'rows': []}))
    assert ina_a5.analyze(LOT)['status'] == 'sin dato'


def test_ruta_nivel_rio(ina):
    from api.index import app
    cl = app.test_client()
    q = '?lat=-28.55&lon=-58.70&polygon=' + json.dumps(LOT)
    r = cl.get('/api/fuentes/nivel-rio' + q)
    j = r.get_json()
    assert r.status_code == 200 and j['data']['reference']['station'] == 'Corrientes'
    assert j['organism'].startswith('INA')
    assert cl.get('/api/fuentes/nivel-rio?lat=-28.55&lon=-58.70').status_code == 400   # sin polígono
    assert cl.get('/api/fuentes/nivel-rio' + q + '&days=9999').status_code == 400      # fuera de rango
