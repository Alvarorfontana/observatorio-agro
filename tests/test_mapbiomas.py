import mapbiomas as mb

LOT = [[-58.71, -28.56], [-58.69, -28.56], [-58.69, -28.54], [-58.71, -28.54]]


def test_countries_for():
    assert mb.countries_for(-58.7, -28.5)[0] == 'argentina'
    assert 'brazil' in mb.countries_for(-50, -15) and 'argentina' not in mb.countries_for(-50, -15)


def test_score_prefers_latest_coverage():
    a = [{'type': 'IMAGE', 'name': 'projects/mapbiomas-public/assets/argentina/collection2/coverage'},
         {'type': 'IMAGE', 'name': 'projects/mapbiomas-public/assets/argentina/lulc/collection_03/integration'},
         {'type': 'IMAGE', 'name': 'projects/mapbiomas-public/assets/argentina/lulc/collection_03/transitions'}]
    found = [x for x in a if mb._score(x)]
    assert len(found) == 2
    assert max(found, key=mb._score)['name'].endswith('collection_03/integration')


def test_parse_image_and_collection():
    img = {'classification_2019': {'3': 60, '15': 40}, 'classification_2020': {'3.0': 50, '15': 50}}
    y = mb.parse(img, {'type': 'IMAGE'})
    assert y[2020] == {3: 50, 15: 50}
    col = {'features': [
        {'properties': {'props': {'year': 2020, 'collection_id': 9}, 'hist': {'classification': {'3': 10}}}},
        {'properties': {'props': {'year': 2020, 'collection_id': 10}, 'hist': {'classification': {'3': 7, '15': 3}}}},
        {'properties': {'props': {'year': 2021, 'collection_id': 10}, 'hist': {'classification': {}}}}]}
    y2 = mb.parse(col, {'type': 'IMAGE_COLLECTION'})
    assert y2 == {2020: {3: 7, 15: 3}}


def test_summarize_eudr():
    years = {1985: {3: 90, 15: 10}, 2020: {3: 60, 15: 40}, 2025: {3: 40, 15: 60}}
    s = mb.summarize(years, 100.0, 'argentina', 'x')
    assert s['first_year'] == 1985 and s['last_year'] == 2025
    assert s['eudr']['forest_cutoff_ha'] == 60.0 and s['eudr']['loss_ha'] == 20.0
    assert s['eudr']['verdict'].startswith('posible pérdida')
    ok = mb.summarize({2020: {3: 60, 15: 40}, 2025: {3: 60, 15: 40}}, 100.0, 'argentina', 'x')
    assert ok['eudr']['verdict'].startswith('sin pérdida')


class _R:
    def __init__(self, code, data): self.status_code = code; self._d = data; self.text = ''
    def json(self): return self._d


def test_history_discovers_and_computes(monkeypatch):
    monkeypatch.setattr(mb, '_ASSET', {})
    monkeypatch.setattr(mb.veg, 'gee_token', lambda: ('proj', 'tok'))
    tree = {'projects/mapbiomas-public/assets/argentina': [{'type': 'FOLDER', 'name': 'projects/mapbiomas-public/assets/argentina/lulc'}],
            'projects/mapbiomas-public/assets/argentina/lulc': [{'type': 'IMAGE', 'name': 'projects/mapbiomas-public/assets/argentina/lulc/collection3_integration_v1'}]}

    class S:
        def get(self, url, **k):
            parent = url.split('/v1/')[1].replace(':listAssets', '')
            return _R(200, {'assets': tree.get(parent, [])})

        def post(self, url, json=None, **k):
            assert json['expression']['values']['out']['functionInvocationValue']['functionName'] == 'Image.reduceRegion'
            return _R(200, {'result': {'classification_2020': {'3': 80, '15': 20}, 'classification_2025': {'3': 80, '15': 20}}})
    monkeypatch.setattr(mb.c, 'SESSION', S())
    out = mb.history(LOT)
    assert out['status'] == 'recibido'
    assert out['data']['country'] == 'argentina' and out['data']['eudr']['verdict'].startswith('sin pérdida')
