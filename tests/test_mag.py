import costs

HTML = '''<html><td>13/10/2026</td><tr><td>Novillos</td><td>$ 2.700,00</td><td>$ 4.840,00</td></tr>
<tr><td>Novillitos</td><td>$ 3.400,00</td><td>$ 5.300,00</td></tr><tr><td>Vacas</td><td>$ 2.100,00</td><td>$ 4.100,00</td></tr>
<div>INMAG</div><div>4.325,41</div><div>IGMAG</div><div>4.154,75</div></html>'''


def test_parse_mag():
    d = costs.parse_mag(HTML)
    assert d['date'] == '13/10/2026'
    nov = next(x for x in d['categories'] if x['category'] == 'Novillos')
    assert nov == {'category': 'Novillos', 'min': 2700.0, 'max': 4840.0}
    assert not any(x['category'] == 'Novillos' and x['min'] == 3400 for x in d['categories'])
    assert d['indices'] == {'INMAG': 4325.41, 'IGMAG': 4154.75}


def test_parse_mag_empty():
    assert costs.parse_mag('<html>sin precios</html>')['categories'] == []
