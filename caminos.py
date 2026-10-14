"""caminos v1.0 — transitabilidad de los caminos alrededor del lote según la lluvia.

Caminos: OpenStreetMap (ODbL) vía Overpass API, en un radio de 8 km del lote. Se separan pavimentados (asfalto,
hormigón, adoquín) de los de tierra, ripio o sin dato de superficie (en zona rural casi siempre son de tierra).
Lluvia: últimas 72 horas y próximas 48 horas en el punto (Open-Meteo).
Rangos orientativos para caminos de tierra (dependen del suelo, del mantenimiento y de cuánto llovió antes):
  menos de 10 mm en 72 h transitable · 10 a 30 mm precaución · 30 a 60 mm riesgo de intransitable ·
  más de 60 mm intransitable para camiones y probablemente para camionetas.
No reemplaza el parte vial de Vialidad ni del municipio.
"""
import math
from datetime import datetime, timezone

import research_connectors as c

OVERPASS = 'https://overpass-api.de/api/interpreter'
FORECAST = 'https://api.open-meteo.com/v1/forecast'
PAVED = {'paved', 'asphalt', 'concrete', 'concrete:plates', 'paving_stones', 'sett', 'chipseal', 'metal'}
GRAVEL = {'gravel', 'fine_gravel', 'compacted', 'pebblestone'}
NAMES = {'trunk': 'Ruta troncal', 'primary': 'Ruta principal', 'secondary': 'Ruta secundaria', 'tertiary': 'Camino terciario',
         'unclassified': 'Camino rural', 'track': 'Huella / camino de campo', 'residential': 'Calle'}


def _km(a, b):
    la1, lo1 = map(math.radians, a); la2, lo2 = map(math.radians, b)
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def kind(tags):
    s = (tags.get('surface') or '').lower()
    if s in PAVED:
        return 'pavimento'
    if s in GRAVEL:
        return 'ripio'
    if s:
        return 'tierra'
    hw = tags.get('highway')
    return 'pavimento' if hw in ('trunk', 'primary', 'motorway') else 'tierra'   # sin dato: en zona rural, casi siempre tierra


def state(rain72):
    if rain72 is None:
        return 'sin dato'
    return 'transitable' if rain72 < 10 else 'precaución' if rain72 < 30 else 'riesgo de intransitable' if rain72 < 60 else 'intransitable'


def roads(lat, lon, radius_m=8000):
    q = (f'[out:json][timeout:25];way(around:{radius_m},{lat},{lon})'
         '["highway"~"^(trunk|primary|secondary|tertiary|unclassified|track|residential)$"];out geom tags;')
    r = c.SESSION.post(OVERPASS, data={'data': q}, timeout=35, headers={'User-Agent': 'DOTS-Campo/1.0 (observatorio-agro.vercel.app)'})
    r.raise_for_status()
    out = []
    for e in r.json().get('elements') or []:
        g = e.get('geometry') or []
        if len(g) < 2:
            continue
        pts = [(p['lat'], p['lon']) for p in g]
        t = e.get('tags') or {}
        out.append({'id': e.get('id'), 'kind': kind(t), 'highway': t.get('highway'), 'name': t.get('name') or t.get('ref') or NAMES.get(t.get('highway'), 'Camino'),
                    'km': sum(_km(a, b) for a, b in zip(pts, pts[1:])), 'line': [[round(a, 5), round(b, 5)] for a, b in pts]})
    return out


def rain(lat, lon):
    js = c._get(FORECAST, {'latitude': lat, 'longitude': lon, 'hourly': 'precipitation', 'past_days': 3, 'forecast_days': 3, 'timezone': 'UTC'}, timeout=20).json()
    h = js.get('hourly') or {}
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:00')
    past = [v for t, v in zip(h.get('time') or [], h.get('precipitation') or []) if t <= now and v is not None][-72:]
    fut = [v for t, v in zip(h.get('time') or [], h.get('precipitation') or []) if t > now and v is not None][:48]
    return (round(sum(past), 1) if len(past) >= 60 else None), (round(sum(fut), 1) if fut else None)


def analyze(lat, lon):
    errors = {}
    try:
        rd = roads(lat, lon)
    except Exception as e:
        rd, errors['caminos'] = [], f'OpenStreetMap no respondió ({type(e).__name__})'
    try:
        r72, r48 = rain(lat, lon)
    except Exception as e:
        r72, r48, errors['lluvia'] = None, None, type(e).__name__
    st = state(r72)
    st_next = state((r72 or 0) * 0.5 + (r48 or 0)) if r48 is not None else None   # lo que quede de la lluvia pasada + la que viene
    km = {k: round(sum(x['km'] for x in rd if x['kind'] == k), 1) for k in ('pavimento', 'ripio', 'tierra')}
    rd.sort(key=lambda x: -x['km'])
    lines = []
    budget = 2500
    for x in rd:
        if budget <= 0:
            break
        lines.append({'kind': x['kind'], 'name': x['name'], 'line': x['line'][:budget]}); budget -= len(x['line'])
    reading = (f"Llovió {r72:.0f} mm en las últimas 72 horas: caminos de tierra {st}." if r72 is not None else 'Sin dato de lluvia reciente.')
    if r48 is not None:
        reading += f" Se pronostican {r48:.0f} mm en las próximas 48 horas" + (f" (en 2 días: {st_next})." if st_next else '.')
    out = {'capability': 'ANALYSIS', 'radius_km': 8, 'km': km, 'total_km': round(sum(km.values()), 1), 'rain_72h_mm': r72, 'rain_next48_mm': r48,
           'state_dirt': st, 'state_dirt_next': st_next, 'reading': reading, 'lines': lines,
           'main_roads': [{'name': x['name'], 'kind': x['kind'], 'km': round(x['km'], 1)} for x in rd[:8]],
           'errors': errors, 'method': __doc__.split('\n\n', 1)[1].strip()}
    ok = bool(rd or r72 is not None)
    return c.envelope(out, OVERPASS, 'caminos y transitabilidad', 'OpenStreetMap (ODbL) · Open-Meteo', 'recibido' if ok else 'sin dato', None if ok else 'Sin datos')
