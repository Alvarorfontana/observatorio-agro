import os
from unittest.mock import patch

import pytest
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


def test_self_intersection_and_holes_and_disjoint():
    import pytest
    with pytest.raises(InputError):
        polygon({'type': 'Polygon', 'coordinates': [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]})
    donut = {'type': 'Polygon', 'coordinates': [rect(0, 0, 2, 2)['coordinates'][0], rect(0.5, 0.5, 1.5, 1.5)['coordinates'][0][::-1]]}
    g = polygon(donut)
    assert abs(area_km2(g) / area_km2(polygon(rect(0, 0, 2, 2))) - 0.75) < 0.01
    r = prepare({**req(), 'hazard': rect(-60, -30, -59.9, -29.9)})
    assert r['intersection'] is None and r['hazard_in_area_km2'] == 0


def test_report_pdf():
    from poblacion import report
    r = prepare(req())
    d = {**r, 'population_total': 131773.9, 'population_exposed': 21197.0, 'exposed_percent': 16.09, 'population_group': 'Población total',
         'source': {'provider': 'WorldPop'}, 'method': 'm', 'interpretation': 'i', 'notes': ['nota']}
    pdf = report.pdf(d)
    assert pdf[:5] == b'%PDF-'
    open('/tmp/claude-0/-home-claude-observatorio-agro/7430de8f-4cd8-57d3-a5ea-bf5e24ee75bb/scratchpad/pob.pdf', 'wb').write(pdf) if os.path.isdir('/tmp/claude-0/-home-claude-observatorio-agro/7430de8f-4cd8-57d3-a5ea-bf5e24ee75bb/scratchpad') else None


def test_crecida_summary_and_expression():
    from poblacion import crecida as cr
    raw = {'total': 400000, 'u5_total': 30000, 'o65_total': 40000}
    for t in cr.BANDS_T:
        raw.update({f'pop_le{t}': t * 10000, f'u5_le{t}': t * 700, f'o65_le{t}': t * 900})
    s = cr.summarize(raw, {'alert': 6.5, 'evac': 7, 'low': 1.83})
    assert s['bands'][0] == {'up_to_m': 1, 'people': 10000, 'under5': 700, 'over65': 900}
    ev = next(x for x in s['scenarios'] if x['key'] == 'evac')
    assert ev['rise_m'] == 5.17 and ev['band_m'] == 10 and ev['people'] == 100000
    assert cr.band_for(4.67) == 5 and cr.band_for(0) is None
    e = cr.expression(-27.47, -58.83)
    assert e['expression']['values']['out']['functionInvocationValue']['functionName'] == 'Image.reduceRegion'


def test_zone_only_without_hazard():
    d = req(); d.pop('hazard')
    r = prepare(d)
    assert r['hazard_given'] is False and r['intersection'] is None and r['hazard'] is None


def test_exposure_reports_missing_signing_key_without_starting_worldpop_tasks(monkeypatch):
    from flask import Flask
    from poblacion import routes

    app = Flask(__name__)
    app.register_blueprint(routes.bp)
    monkeypatch.setattr(routes, '_signing_key', lambda: None)
    monkeypatch.setenv('DOTS_POPULATION_SIGNING_KEY', '')
    monkeypatch.setenv('GOOGLE_APPLICATION_CREDENTIALS_JSON', '')
    monkeypatch.setenv('CDSE_CLIENT_SECRET', '')
    monkeypatch.setenv('SENTINEL_HUB_CLIENT_SECRET', '')
    monkeypatch.setenv('DMC_TOKEN', '')
    monkeypatch.setenv('WHISP_API_KEY', '')
    monkeypatch.setattr(worldpop, 'submit', lambda *args, **kwargs: pytest.fail('No debe iniciar tareas sin firma'))

    response = app.test_client().post('/api/poblacion/exposicion', json=req())
    assert response.status_code == 503
    assert 'firma' in response.get_json()['error']
