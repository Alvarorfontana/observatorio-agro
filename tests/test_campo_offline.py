import campo_offline as co


def test_payload_roundtrip_and_qr():
    cells = [[-36.30 + i * 0.001, -58.40 + j * 0.001, 'loma' if j > 5 else 'bajo'] for i in range(20) for j in range(12)]
    risk = {'zones': [{'key': 'loma', 'name': 'Loma', 'color': '#c9a227', 'pct': 50.0, 'ha': 10.0}, {'key': 'bajo', 'name': 'Bajo', 'color': '#4fa3d1', 'pct': 50.0, 'ha': 10.0}],
            'grid': {'cells': cells, 'dlat': 0.001, 'dlon': 0.001}}
    poly = [[-36.30, -58.40], [-36.30, -58.388], [-36.281, -58.388], [-36.281, -58.40]]
    url, factor = co.payload('La Esperanza', poly, risk, [['Suelo', 'Ar1']])
    assert url.startswith(co.SITE + '/campo#d=') and factor == 1 and len(url.split('#d=')[1]) <= co.MAX_HASH
    d = co.decode(url.split('#d=')[1])
    assert d['n'] == 'La Esperanza' and d['z']['r'] == 20 and d['z']['c'] == 12 and d['z']['g'][0] == 'B' and d['z']['g'][11] == 'L'
    assert ['Suelo', 'Ar1'] in d['s']
    assert co.qr_svg(url).startswith('<svg') and '<rect' in co.zones_svg(risk, poly)
