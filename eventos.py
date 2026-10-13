"""eventos — eventos extremos alrededor de la Cuenca del Plata (portado de AgroClima v3, del lado del servidor).

  · Ciclones tropicales y subtropicales activos: NOAA NCEI IBTrACS, archivo ACTIVE (últimos días, todo el mundo,
    incluye el Atlántico Sur). Se informa la última posición de cada sistema y su distancia al punto.
  · Alertas de la ONU y la Comisión Europea (GDACS): ciclones, inundaciones, sequías, incendios y sismos activos
    en Argentina, Uruguay, Paraguay, Brasil, Bolivia y Chile.
Ambos son abiertos y sin clave; desde el navegador fallan por CORS, por eso se consultan acá.
"""
import csv, io, math, re, time

import research_connectors as c

IBTRACS = 'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ACTIVE.list.v04r01.csv'
GDACS = 'https://www.gdacs.org/xml/rss.xml'
PAISES = {'argentina': 'Argentina', 'uruguay': 'Uruguay', 'paraguay': 'Paraguay', 'brazil': 'Brasil', 'bolivia': 'Bolivia', 'chile': 'Chile'}
TIPOS = {'TC': 'Ciclón tropical', 'FL': 'Inundación', 'DR': 'Sequía', 'WF': 'Incendio forestal', 'EQ': 'Sismo', 'VO': 'Volcán', 'TS': 'Tsunami'}
NIVELES = {'green': 'Verde', 'orange': 'Naranja', 'red': 'Rojo'}
_CACHE = {}


def dist_km(a, b, c_, d):
    r = math.radians
    h = math.sin(r(c_ - a) / 2) ** 2 + math.cos(r(a)) * math.cos(r(c_)) * math.sin(r(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def categoria(kt):
    if kt is None: return 'sin dato de viento'
    if kt < 34: return 'depresión'
    if kt < 64: return 'tormenta'
    for lim, cat in ((83, 1), (96, 2), (113, 3), (137, 4)):
        if kt < lim: return f'huracán categoría {cat}'
    return 'huracán categoría 5'


def parse_ibtracs(text):
    """Última posición de cada sistema. La segunda fila del archivo trae las unidades y se saltea."""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    head = rows[0]; ix = {k: head.index(k) for k in ('SID', 'ISO_TIME', 'LAT', 'LON', 'NAME', 'BASIN', 'USA_WIND', 'WMO_WIND', 'WMO_PRES', 'USA_PRES') if k in head}
    last = {}
    for r in rows[1:]:
        if len(r) <= max(ix.values()) or not r[ix['SID']] or r[ix['ISO_TIME']].startswith(('Year', ' ')):
            continue
        try:
            lat, lon = float(r[ix['LAT']]), float(r[ix['LON']])
        except ValueError:
            continue
        sid = r[ix['SID']]
        if sid not in last or r[ix['ISO_TIME']] > last[sid]['time']:
            num = lambda k: float(r[ix[k]]) if k in ix and r[ix[k]].strip() not in ('', ' ') and re.match(r'^-?\d', r[ix[k]].strip()) else None
            wind = num('WMO_WIND') or num('USA_WIND')
            last[sid] = {'id': sid, 'time': r[ix['ISO_TIME']], 'lat': lat, 'lon': lon, 'name': (r[ix['NAME']] or 'SIN NOMBRE').title(),
                         'basin': r[ix.get('BASIN', 0)], 'wind_kt': wind, 'wind_kmh': round(wind * 1.852) if wind else None,
                         'pressure': num('WMO_PRES') or num('USA_PRES'), 'category': categoria(wind)}
    return list(last.values())


def parse_gdacs(xml):
    out = []
    for b in xml.split('<item>')[1:]:
        def tag(t):
            m = re.search(rf'<{t}[^>]*>(.*?)</{t}>', b, re.S)
            return re.sub(r'<!\[CDATA\[|\]\]>', '', m.group(1)).strip() if m else ''
        pais = tag('gdacs:country').lower()
        paises = [v for k, v in PAISES.items() if k in pais]
        if not paises:
            continue
        lat = lon = None
        m = re.search(r'<geo:Point>\s*<geo:lat>([-\d.]+)</geo:lat>\s*<geo:long>([-\d.]+)</geo:long>', b)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
        tipo = tag('gdacs:eventtype')
        out.append({'title': tag('title'), 'type': TIPOS.get(tipo, tipo), 'level': NIVELES.get(tag('gdacs:alertlevel').lower(), tag('gdacs:alertlevel')),
                    'countries': paises, 'date': tag('pubDate'), 'link': tag('link'), 'lat': lat, 'lon': lon,
                    'severity': re.sub(r'\s+', ' ', tag('gdacs:severity'))[:160]})
    return out


def extremos(lat, lon):
    key = 'extremos'
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < 3 * 3600:
        raw = hit[1]
    else:
        raw = {'ciclones': None, 'gdacs': None, 'errors': {}}
        try:
            r = c.SESSION.get(IBTRACS, timeout=30); r.raise_for_status()
            if r.text.lstrip().startswith('<'):
                raise ValueError('IBTrACS devolvió una página en vez del archivo')
            raw['ciclones'] = parse_ibtracs(r.text)
        except Exception as e:
            raw['errors']['ibtracs'] = type(e).__name__
        try:
            r = c.SESSION.get(GDACS, timeout=30); r.raise_for_status()
            raw['gdacs'] = parse_gdacs(r.text)
        except Exception as e:
            raw['errors']['gdacs'] = type(e).__name__
        if raw['ciclones'] is not None or raw['gdacs'] is not None:
            _CACHE[key] = (time.monotonic(), raw)
    cic = [dict(x, distance_km=round(dist_km(lat, lon, x['lat'], x['lon']))) for x in raw['ciclones'] or []]
    cic.sort(key=lambda x: x['distance_km'])
    gd = [dict(x, distance_km=round(dist_km(lat, lon, x['lat'], x['lon'])) if x['lat'] is not None else None) for x in raw['gdacs'] or []]
    ok = raw['ciclones'] is not None or raw['gdacs'] is not None
    return c.envelope({'cyclones': cic, 'near': [x for x in cic if x['distance_km'] <= 2500], 'gdacs': gd, 'errors': raw['errors']},
                      'multi', 'ciclones activos y alertas de desastres', 'NOAA NCEI IBTrACS · GDACS (ONU y Comisión Europea)',
                      'recibido' if ok else 'sin dato', None if ok else 'IBTrACS y GDACS no respondieron')
