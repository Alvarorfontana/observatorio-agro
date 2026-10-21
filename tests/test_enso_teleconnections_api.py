from flask import Flask
import enso_data_api as api
from tools import import_noaa_teleconnections as importer


def test_teleconnections_returns_source_and_observations(monkeypatch):
    monkeypatch.setattr(importer, 'collect', lambda: {
        'provider': 'NOAA Physical Sciences Laboratory',
        'status': {'soi': 'ok'},
        'indices': {'soi': {'source': 'https://psl.noaa.gov/data/correlation/soi.data',
                            'observations': [{'month': '2025-01', 'value': 1.2}]}}
    })
    monkeypatch.setitem(api._TELE_CACHE, 'data', None)
    app = Flask(__name__)
    app.register_blueprint(api.enso_data_api)
    response = app.test_client().get('/api/enso/teleconnections')
    assert response.status_code == 200
    assert response.get_json()['indices']['soi']['observations'][0]['value'] == 1.2


def test_teleconnections_no_data_returns_503(monkeypatch):
    monkeypatch.setattr(importer, 'collect', lambda: {'indices': {}, 'status': {}})
    monkeypatch.setitem(api._TELE_CACHE, 'data', None)
    app = Flask(__name__)
    app.register_blueprint(api.enso_data_api)
    response = app.test_client().get('/api/enso/teleconnections')
    assert response.status_code == 503
