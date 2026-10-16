import suelos_ba, catastro, datastore


def test_soils_overlap(monkeypatch):
    tile = {'f': [[0, [-58.5, -36.5, -58.4, -36.4], [[[-58.5, -36.5], [-58.4, -36.5], [-58.4, -36.4], [-58.5, -36.4], [-58.5, -36.5]]]],
                  [1, [-58.4, -36.5, -58.3, -36.4], [[[-58.4, -36.5], [-58.3, -36.5], [-58.3, -36.4], [-58.4, -36.4], [-58.4, -36.5]]]]]}
    units = {'0': {'s': 'Ar1', 'n': 'Consociación Arroyo', 'comp': 'Arroyo 80 %', 'cap': 'IIw', 'tax': 'Argiudol ácuico', 'pai': 'Plano'},
             '1': {'s': 'Bo2', 'n': 'Asociación Bosque', 'comp': 'Bosque 60 %', 'cap': 'IVws', 'tax': 'Natracualf', 'pai': 'Bajo'}}
    monkeypatch.setattr(datastore, 'load', lambda name, default=None, branch=None, ttl=None: units if name.endswith('unidades.json') else tile)
    poly = [[-36.48, -58.45], [-36.48, -58.37], [-36.42, -58.37], [-36.42, -58.45]]   # 5/8 en Ar1, 3/8 en Bo2
    d = suelos_ba.at_polygon(poly)
    assert [u['symbol'] for u in d['units']] == ['Ar1', 'Bo2']
    assert abs(d['units'][0]['pct'] - 62.5) < 1 and 'Ar1' in d['reading']
    assert suelos_ba.at_polygon([[-28.5, -59.0], [-28.5, -58.9], [-28.6, -58.9]]) is None   # fuera de Buenos Aires


def test_catastro_outside_and_parse(monkeypatch):
    assert catastro.parcel_at(-28.5, -59.0)['status'] == 'sin dato'
    class R:
        def raise_for_status(self): pass
        def json(self): return {'features': [{'id': 'Parcela.X', 'geometry': {'type': 'MultiPolygon', 'coordinates': [[[[-58.42, -36.32], [-58.38, -36.32], [-58.38, -36.28], [-58.42, -36.28], [-58.42, -36.32]]]]},
                                              'properties': {'cca': 'X', 'pda': '083002273', 'tpa': 'Rural', 'ara1': 6903767.1}}]}
    monkeypatch.setattr(catastro.c.SESSION, 'get', lambda *a, **k: R())
    d = catastro.parcel_at(-36.30, -58.40)['data']
    assert d['partida'] == '083002273' and d['area_ha'] == 690.38 and len(d['polygon']) == 4 and d['polygon'][0] == [-36.32, -58.42]
