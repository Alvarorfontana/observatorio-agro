"""Guardado de lotes en el repositorio privado y lectura de resultados (GitHub simulado)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import lotes_store as ls

LOT = {'id': 'lote-123-abcde', 'name': 'Potrero Norte', 'vertices': [[-28.5, -59.0], [-28.5, -59.01], [-28.51, -59.01]], 'areaHa': 100.123, 'extra': 'no'}


@pytest.fixture
def client(monkeypatch):
    from api.index import app
    monkeypatch.setenv('DOTS_DATA_REPO', 'yo/dots-datos')
    monkeypatch.setenv('DOTS_DATA_TOKEN', 't')
    monkeypatch.setenv('DOTS_WRITE_KEY', 'clave-secreta')
    store = {}
    monkeypatch.setattr(ls, '_read', lambda path: (store.get(path), 'sha' if path in store else None))
    def write(path, data, sha, message): store[path] = data
    monkeypatch.setattr(ls, '_write', write)
    c = app.test_client(); c.store = store
    return c


def test_clean_lot_valida_y_recorta_campos():
    l = ls.clean_lot(LOT)
    assert set(l) == {'id', 'name', 'vertices', 'areaHa'} and l['areaHa'] == 100.12
    for bad in ({**LOT, 'id': '../x'}, {**LOT, 'vertices': [[1, 2]]}, {**LOT, 'vertices': [[95, 0], [0, 0], [1, 1]]}):
        with pytest.raises(ValueError):
            ls.clean_lot(bad)


def test_merge_actualiza_por_id_y_quita():
    a = {'id': 'lote-aaaa', 'name': 'A'}; b = {'id': 'lote-bbbb', 'name': 'B'}
    out = ls.merge_lots([a, b], [{'id': 'lote-aaaa', 'name': 'A2'}], remove=['lote-bbbb'])
    assert out == [{'id': 'lote-aaaa', 'name': 'A2'}]


def test_sin_configurar_responde_503(monkeypatch):
    from api.index import app
    for k in ('DOTS_DATA_REPO', 'DOTS_DATA_TOKEN', 'DOTS_WRITE_KEY'):
        monkeypatch.delenv(k, raising=False)
    c = app.test_client()
    assert c.get('/api/lotes/estado').get_json() == {'configured': False}
    assert c.post('/api/lotes/sincronizar', json={'lotes': [LOT]}).status_code == 503


def test_clave_incorrecta_rechaza(client):
    r = client.post('/api/lotes/sincronizar', json={'lotes': [LOT]}, headers={'X-DOTS-Key': 'otra'})
    assert r.status_code == 401 and 'lotes.json' not in client.store


def test_sincroniza_y_lee_resultado(client):
    h = {'X-DOTS-Key': 'clave-secreta'}
    r = client.post('/api/lotes/sincronizar', json={'lotes': [LOT]}, headers=h)
    assert r.status_code == 200 and r.get_json()['lotes'] == 1
    assert client.store['lotes.json']['lotes'][0]['name'] == 'Potrero Norte' and 'extra' not in client.store['lotes.json']['lotes'][0]
    assert client.get('/api/lotes/resultado?id=lote-123-abcde', headers=h).get_json()['status'] == 'pendiente'
    client.store['resultados/lote-123-abcde.json'] = {'status': 'recibido', 'water_ha': 3.2}
    assert client.get('/api/lotes/resultado?id=lote-123-abcde', headers=h).get_json()['water_ha'] == 3.2
    assert client.get('/api/lotes/resultado?id=../../x', headers=h).status_code == 400
