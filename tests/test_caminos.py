import caminos as cm


def test_kind_and_state():
    assert cm.kind({'surface': 'asphalt'}) == 'pavimento' and cm.kind({'surface': 'gravel'}) == 'ripio'
    assert cm.kind({'highway': 'track'}) == 'tierra' and cm.kind({'highway': 'primary'}) == 'pavimento'
    assert cm.state(5) == 'transitable' and cm.state(45) == 'riesgo de intransitable' and cm.state(80) == 'intransitable'


def test_analyze(monkeypatch):
    monkeypatch.setattr(cm, 'roads', lambda la, lo: [{'id': 1, 'kind': 'tierra', 'highway': 'track', 'name': 'Huella', 'km': 3.2, 'line': [[-28.5, -58.7], [-28.51, -58.71]]},
                                                     {'id': 2, 'kind': 'pavimento', 'highway': 'primary', 'name': 'RN 12', 'km': 8.0, 'line': [[-28.5, -58.6], [-28.6, -58.6]]}])
    monkeypatch.setattr(cm, 'rain', lambda la, lo: (42.0, 20.0))
    d = cm.analyze(-28.5, -58.7)['data']
    assert d['km'] == {'pavimento': 8.0, 'ripio': 0, 'tierra': 3.2} and d['state_dirt'] == 'riesgo de intransitable'
    assert 'Llovió 42 mm' in d['reading'] and d['main_roads'][0]['name'] == 'RN 12'
