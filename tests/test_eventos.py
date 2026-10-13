"""Eventos extremos (IBTrACS, GDACS) y tránsito de crecidas entre puertos, con fuentes simuladas."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import eventos

CSV = """SID,SEASON,NUMBER,BASIN,SUBBASIN,NAME,ISO_TIME,NATURE,LAT,LON,WMO_WIND,WMO_PRES,USA_WIND,USA_PRES
 ,Year,,,,,,,degrees_north,degrees_east,kts,mb,kts,mb
2026280S30320,2026,1,SA,MM,AKARA,2026-10-07 00:00:00,TS,-30.0,-40.0,40,1000, ,
2026280S30320,2026,1,SA,MM,AKARA,2026-10-08 00:00:00,TS,-31.0,-42.0,55,995, ,
2026275N15300,2026,9,NA,MM,ZETA,2026-10-08 06:00:00,TS,20.0,-60.0, , ,90,960
"""
RSS = """<rss><channel><item><title>Inundación en Argentina</title><gdacs:eventtype>FL</gdacs:eventtype><gdacs:alertlevel>Orange</gdacs:alertlevel>
<gdacs:country>Argentina</gdacs:country><pubDate>Mon, 12 Oct 2026</pubDate><link>https://gdacs.org/x</link>
<geo:Point><geo:lat>-29.1</geo:lat><geo:long>-59.3</geo:long></geo:Point><gdacs:severity>Magnitude 2</gdacs:severity></item>
<item><title>Sismo en Japón</title><gdacs:eventtype>EQ</gdacs:eventtype><gdacs:alertlevel>Green</gdacs:alertlevel><gdacs:country>Japan</gdacs:country></item></channel></rss>"""


def test_parsers():
    cs = {x['name']: x for x in eventos.parse_ibtracs(CSV)}
    assert cs['Akara']['time'].startswith('2026-10-08') and cs['Akara']['wind_kt'] == 55 and cs['Akara']['category'] == 'tormenta'
    assert cs['Zeta']['category'] == 'huracán categoría 2' and cs['Zeta']['wind_kmh'] == 167
    g = eventos.parse_gdacs(RSS)
    assert len(g) == 1 and g[0]['type'] == 'Inundación' and g[0]['level'] == 'Naranja' and g[0]['lat'] == -29.1


def test_extremos_y_ruta(monkeypatch):
    eventos._CACHE.clear()
    class R:
        def __init__(self, t): self.text = t
        def raise_for_status(self): pass
    monkeypatch.setattr(eventos.c.SESSION, 'get', lambda url, timeout=30: R(CSV if 'ibtracs' in url else RSS))
    d = eventos.extremos(-29.1, -59.3)['data']
    assert d['near'][0]['name'] == 'Akara' and d['gdacs'][0]['distance_km'] == 0
    from api.index import app
    cl = app.test_client()
    j = cl.get('/api/fuentes/transito-crecida?desde=parana-corrientes&hasta=parana-goya').get_json()
    assert j['status'] == 'recibido' and [t['hasta'] for t in j['data']['tramos']] == ['Bella Vista', 'Goya']
    j = cl.get('/api/fuentes/transito-crecida?desde=parana-goya&hasta=parana-corrientes').get_json()
    assert j['status'] == 'sin dato'
    j = cl.get('/api/fuentes/transito-crecida?desde=paraguay-asuncion&hasta=parana-goya').get_json()
    assert j['data']['tramos'][0]['desde'] == 'Asunción' and j['data']['tramos'][-1]['hasta'] == 'Goya'
