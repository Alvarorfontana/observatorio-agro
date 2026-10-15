import json, os
import datastore


def _app():
    from flask import Flask
    from research_routes import research_api
    app = Flask(__name__); app.register_blueprint(research_api)
    return app.test_client()


def test_route_without_data(monkeypatch):
    monkeypatch.setattr(datastore, 'load', lambda name, default=None: None)
    r = _app().get('/api/fuentes/rinde-agua')
    assert r.status_code == 404 and 'todavía no corrió' in r.get_json()['error']


def test_route_with_data(monkeypatch):
    sample = {'season': '2026/27', 'places': {'pergamino': {'name': 'Pergamino', 'maiz': {'normal': {'p50': 0.87}, 'outlook': {'p50': 0.99, 'below': 0.1}}}}}
    monkeypatch.setattr(datastore, 'load', lambda name, default=None: sample if name == 'rinde_agua.json' else default)
    j = _app().get('/api/fuentes/rinde-agua').get_json()
    assert j['status'] == 'recibido' and j['data']['places']['pergamino']['maiz']['outlook']['p50'] == 0.99


def test_percentile_and_season():
    import importlib.util
    spec = importlib.util.spec_from_file_location('ra', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'rinde_agua.py'))
    ra = importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
    from datetime import date
    assert ra.season_of(date(2026, 10, 15)) == 2026 and ra.season_of(date(2027, 3, 1)) == 2026
    assert ra.pct([1, 2, 3, 4, 5], .5) == 3 and ra.pct([0, 10], .1) == 1
