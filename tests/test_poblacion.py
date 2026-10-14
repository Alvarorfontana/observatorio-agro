import os
from unittest.mock import patch

from poblacion.geometry import prepare, InputError, polygon, area_km2
from poblacion import worldpop


def rect(w, s, e, n):
    return {'type': 'Polygon', 'coordinates': [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def req():
    return {'area': rect(-58.85, -27.48, -58.83, -27.46), 'hazard': rect(-58.85, -27.48, -58.84, -27.46), 'year': 2025,
            'event': {'kind': 'inundacion', 'category': 'escenario_usuario', 'source': 'Prueba', 'date': '2026-10-14', 'enso': 'el_nino'}}


def test_intersection_half():
    r = prepare(req())
    assert abs(r['hazard_in_area_km2'] / r['area_km2'] - 0.5) < 1e-3


def test_area_close_to_ellipsoid():
    # 1° x 1° en el ecuador ≈ 12.308 km² (WGS84)
    a = area_km2(polygon(rect(0, 0, 1, 1)))
    assert abs(a - 12308) / 12308 < 0.005


def test_invalid_inputs():
    import pytest
    for change in ({'area': rect(0, 0, 0, 0)}, {'year': True}, {'year': 2000}, {'event': {'date': 'bad'}}):
        with pytest.raises(InputError):
            prepare({**req(), **change})


def test_worldpop_poll():
    assert worldpop.poll('abc', transport=lambda p, b=None: {'status': 'pending'}) == {'status': 'pending'}
    assert worldpop.poll('abc', transport=lambda p, b=None: {'status': 'success', 'result': {'total_population': 1234.5}})['population'] == 1234.5


def test_routes_flow(monkeypatch):
    os.environ['DOTS_DISABLE_RATE_LIMIT'] = '1'
    monkeypatch.setenv('DOTS_POPULATION_SIGNING_KEY', 'x' * 32)
    import importlib, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from api.index import app
    c = app.test_client()
    assert c.get('/api/poblacion/estado').get_json()['worldpop'] == 'ready'
    assert c.get('/api/poblacion/datasets').get_json()['datasets'][0]['id'] == 'worldpop-api'
    calls = []

    def fake_call(path, payload=None):
        calls.append(path)
        if path == '/population':
            return {'task_id': f't{len(calls)}'}
        return {'status': 'success', 'result': {'total_population': 1000.0 if path.endswith('t1') else 400.0}}
    with patch.object(worldpop, 'call', fake_call), patch.object(worldpop, 'submit', lambda g, y, transport=fake_call: worldpop.__dict__['_submit'](g, y, fake_call) if '_submit' in worldpop.__dict__ else fake_call('/population')['task_id']), \
         patch.object(worldpop, 'poll', lambda t, transport=fake_call: {'status': 'complete', 'population': 1000.0 if t == 't1' else 400.0}):
        r = c.post('/api/poblacion/exposicion', json=req())
        assert r.status_code == 202
        tok = r.get_json()['token']
        res = c.post('/api/poblacion/resultado', json={'token': tok}).get_json()
    assert res['status'] == 'complete' and res['population_exposed'] == 400.0 and round(res['exposed_percent']) == 40
