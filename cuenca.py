"""cuenca — Cuenca del Plata: El Niño semanal, lluvia en las cabeceras y caudal de los grandes ríos.

Tres piezas abiertas y gratuitas, cada una falla por separado sin inventar datos:
  1. El Niño semanal (NOAA CPC, OISST): regiones Niño 1+2 (costero, frente a Perú), 3, 3.4 y 4.
  2. Lluvia de los próximos 15 días en 21 subcuencas que aportan al Paraná, Paraguay, Iguazú,
     Uruguay, Bermejo y Pilcomayo (Brasil, Paraguay, Bolivia, Uruguay y el norte argentino) con el pronóstico por conjunto de ECMWF (51 corridas) y GFS (31) vía Open-Meteo:
     mediana, rango y probabilidad de superar 50 y 100 mm, contra lo normal de esos 15 días.
  4. Represas de Brasil (ONS, datos abiertos): caudal medido que sueltan Salto Caxias (Iguazú),
     Itaipú y Porto Primavera (Paraná), Itá y Foz do Chapecó (Uruguay).
  3. Caudal de hoy y pronóstico a 30 días en Iguazú, Paraná, Paraguay y Uruguay (GloFAS,
     Copernicus, vía Open-Meteo), comparado con lo normal para la fecha (2001-2020).
Las normales se calculan una vez con scripts/normales_cuenca.py (GitHub Actions) y se guardan en
data/cuenca_normales.json, así la web no gasta consultas pesadas en cada visita.
"""
import json, math, os, re, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import research_connectors as c

CPC_WEEKLY = 'https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for'
ENSEMBLE = 'https://ensemble-api.open-meteo.com/v1/ensemble'
FLOOD = 'https://flood-api.open-meteo.com/v1/flood'
NORMALS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cuenca_normales.json')

# Cabeceras: puntos que representan dónde llueve y nace la crecida (promedio de los puntos).
BASINS = [
    {'id': 'alto-iguazu', 'group': 'Iguazú', 'name': 'Alto Iguazú', 'where': 'Curitiba a União da Vitória (Paraná, Brasil)', 'outlet': 'iguazu-cataratas', 'response': (3, 6), 'travel': 'a Cataratas en 3 a 6 días', 'points': [(-25.43, -49.27), (-26.23, -51.09)]},
    {'id': 'medio-iguazu', 'group': 'Iguazú', 'name': 'Iguazú medio y bajo', 'where': 'Guarapuava, Chopim y sudoeste de Paraná (Brasil)', 'outlet': 'iguazu-cataratas', 'response': (1, 3), 'travel': 'a Cataratas en 1 a 3 días', 'points': [(-25.39, -51.46), (-25.67, -53.81)]},
    {'id': 'paranaiba', 'group': 'Paraná', 'name': 'Paranaíba', 'where': 'Goiás y Triângulo Mineiro (Brasil)', 'outlet': 'parana-posadas', 'response': (10, 20), 'travel': 'regulado por represas; a Posadas en 10 a 20 días', 'points': [(-16.68, -49.25), (-18.92, -48.28)]},
    {'id': 'grande', 'group': 'Paraná', 'name': 'Río Grande', 'where': 'Minas Gerais y norte de São Paulo (Brasil)', 'outlet': 'parana-posadas', 'response': (10, 20), 'travel': 'regulado por represas; a Posadas en 10 a 20 días', 'points': [(-21.24, -45.0), (-20.54, -47.4)]},
    {'id': 'tiete', 'group': 'Paraná', 'name': 'Tietê', 'where': 'São Paulo (Brasil)', 'outlet': 'parana-posadas', 'response': (8, 16), 'travel': 'a Posadas en 8 a 16 días', 'points': [(-23.55, -46.63), (-22.31, -49.06)]},
    {'id': 'paranapanema', 'group': 'Paraná', 'name': 'Paranapanema', 'where': 'límite São Paulo y Paraná (Brasil)', 'outlet': 'parana-posadas', 'response': (6, 12), 'travel': 'a Posadas en 6 a 12 días', 'points': [(-23.98, -48.88), (-22.98, -49.87)]},
    {'id': 'ivai-piquiri', 'group': 'Paraná', 'name': 'Ivaí y Piquiri', 'where': 'oeste de Paraná (Brasil), llegan antes de Itaipú', 'outlet': 'parana-posadas', 'response': (4, 8), 'travel': 'a Posadas en 4 a 8 días', 'points': [(-23.77, -53.32), (-24.96, -53.46)]},
    {'id': 'cuiaba', 'group': 'Paraguay', 'name': 'Cuiabá', 'where': 'Mato Grosso (Brasil) · norte del Pantanal', 'outlet': 'paraguay-asuncion', 'response': (30, 90), 'travel': 'el Pantanal retiene: a Asunción en 1 a 3 meses', 'points': [(-15.6, -56.1), (-14.84, -56.43)]},
    {'id': 'taquari-miranda', 'group': 'Paraguay', 'name': 'Taquari y Miranda', 'where': 'Mato Grosso do Sul (Brasil) · sur del Pantanal', 'outlet': 'paraguay-asuncion', 'response': (20, 60), 'travel': 'a Asunción en 3 a 8 semanas', 'points': [(-18.51, -54.76), (-20.47, -55.79)]},
    {'id': 'apa-aquidaban', 'group': 'Paraguay', 'name': 'Apa, Aquidabán e Ypané', 'where': 'frontera Brasil–Paraguay y Concepción', 'outlet': 'paraguay-asuncion', 'response': (4, 10), 'travel': 'a Asunción en 4 a 10 días', 'points': [(-22.11, -56.52), (-23.4, -57.43)]},
    {'id': 'jejui', 'group': 'Paraguay', 'name': 'Jejuí y Manduvirá', 'where': 'San Pedro y Canindeyú (Paraguay)', 'outlet': 'paraguay-asuncion', 'response': (3, 8), 'travel': 'a Asunción en 3 a 8 días', 'points': [(-24.65, -56.44), (-24.47, -55.7)]},
    {'id': 'tebicuary', 'group': 'Paraguay', 'name': 'Tebicuary', 'where': 'Guairá, Caazapá y Misiones (Paraguay)', 'outlet': 'paraguay-pilar', 'response': (3, 10), 'travel': 'a Pilar en 3 a 10 días', 'points': [(-25.75, -56.43), (-26.67, -57.15)]},
    {'id': 'pilcomayo', 'group': 'Bermejo y Pilcomayo', 'name': 'Pilcomayo', 'where': 'Potosí, Chuquisaca y Tarija (Bolivia) · norte de Salta', 'outlet': 'paraguay-asuncion', 'response': (20, 60), 'travel': 'se pierde en bañados; aporte lento al Paraguay', 'points': [(-19.58, -65.75), (-21.26, -63.47)]},
    {'id': 'bermejo-bolivia', 'group': 'Bermejo y Pilcomayo', 'name': 'Bermejo superior', 'where': 'Tarija (Bolivia)', 'outlet': 'bermejo-elcolorado', 'response': (8, 18), 'travel': 'a El Colorado en 1 a 3 semanas y luego al Paraguay', 'points': [(-21.53, -64.73), (-22.73, -64.34)]},
    {'id': 'bermejo-salta', 'group': 'Bermejo y Pilcomayo', 'name': 'Bermejo · Salta y Jujuy', 'where': 'Orán, San Francisco y Ledesma (Argentina)', 'outlet': 'bermejo-elcolorado', 'response': (5, 12), 'travel': 'a El Colorado en 5 a 12 días y luego al Paraguay', 'points': [(-23.13, -64.33), (-23.83, -64.79)]},
    {'id': 'pelotas-canoas', 'group': 'Uruguay', 'name': 'Pelotas y Canoas', 'where': 'sierra de Santa Catarina y Rio Grande do Sul (Brasil)', 'outlet': 'uruguay-soberbio', 'response': (4, 8), 'travel': 'a El Soberbio en 4 a 8 días', 'points': [(-27.82, -50.33), (-28.51, -50.93)]},
    {'id': 'uruguay-medio', 'group': 'Uruguay', 'name': 'Uruguay medio', 'where': 'Chapecó, Erechim y Joaçaba (Brasil)', 'outlet': 'uruguay-soberbio', 'response': (3, 6), 'travel': 'a El Soberbio en 3 a 6 días', 'points': [(-27.1, -52.62), (-27.17, -51.5)]},
    {'id': 'peperi', 'group': 'Uruguay', 'name': 'Peperi-Guaçu y Misiones', 'where': 'oeste de Santa Catarina y Misiones', 'outlet': 'uruguay-soberbio', 'response': (1, 4), 'travel': 'a El Soberbio en 1 a 4 días', 'points': [(-26.73, -53.52), (-27.3, -54.2)]},
    {'id': 'ijui', 'group': 'Uruguay', 'name': 'Ijuí y Piratinim', 'where': 'noroeste de Rio Grande do Sul (Brasil)', 'outlet': 'uruguay-santotome', 'response': (2, 5), 'travel': 'a Santo Tomé en 2 a 5 días', 'points': [(-28.39, -53.91), (-28.3, -54.26)]},
    {'id': 'ibicui', 'group': 'Uruguay', 'name': 'Ibicuí', 'where': 'centro-oeste de Rio Grande do Sul (Brasil)', 'outlet': 'uruguay-libres', 'response': (3, 8), 'travel': 'a Paso de los Libres en 3 a 8 días', 'points': [(-29.69, -53.81), (-29.78, -55.79)]},
    {'id': 'cuareim-arapey', 'group': 'Uruguay', 'name': 'Cuareim y Arapey', 'where': 'norte de Uruguay y frontera con Brasil', 'outlet': 'uruguay-montecaseros', 'response': (2, 5), 'travel': 'a Monte Caseros en 2 a 5 días', 'points': [(-30.4, -56.47), (-30.95, -57.0)]},
]


# Ríos: punto sobre el cauce principal (la celda GloFAS elegida se guarda en las normales).
STATIONS = [
    {'id': 'iguazu-andresito', 'river': 'Iguazú', 'place': 'Andresito', 'lat': -25.58, 'lon': -53.99},
    {'id': 'iguazu-cataratas', 'river': 'Iguazú', 'place': 'Puerto Iguazú · Cataratas', 'lat': -25.6, 'lon': -54.38},
    {'id': 'parana-eldorado', 'river': 'Paraná', 'place': 'Eldorado', 'lat': -26.4, 'lon': -54.69},
    {'id': 'parana-posadas', 'river': 'Paraná', 'place': 'Posadas', 'lat': -27.36, 'lon': -55.9},
    {'id': 'parana-ituzaingo', 'river': 'Paraná', 'place': 'Ituzaingó', 'lat': -27.58, 'lon': -56.69},
    {'id': 'parana-corrientes', 'river': 'Paraná', 'place': 'Corrientes', 'lat': -27.46, 'lon': -58.85},
    {'id': 'parana-bellavista', 'river': 'Paraná', 'place': 'Bella Vista', 'lat': -28.51, 'lon': -59.05},
    {'id': 'parana-goya', 'river': 'Paraná', 'place': 'Goya', 'lat': -29.14, 'lon': -59.3},
    {'id': 'parana-reconquista', 'river': 'Paraná', 'place': 'Reconquista', 'lat': -29.24, 'lon': -59.58},
    {'id': 'parana-esquina', 'river': 'Paraná', 'place': 'Esquina', 'lat': -30.01, 'lon': -59.55},
    {'id': 'parana-lapaz', 'river': 'Paraná', 'place': 'La Paz', 'lat': -30.74, 'lon': -59.65},
    {'id': 'parana-santafe', 'river': 'Paraná', 'place': 'Santa Fe · Paraná', 'lat': -31.7, 'lon': -60.55},
    {'id': 'parana-diamante', 'river': 'Paraná', 'place': 'Diamante', 'lat': -32.07, 'lon': -60.64},
    {'id': 'parana-rosario', 'river': 'Paraná', 'place': 'Rosario', 'lat': -32.95, 'lon': -60.62},
    {'id': 'parana-sannicolas', 'river': 'Paraná', 'place': 'San Nicolás', 'lat': -33.33, 'lon': -60.2},
    {'id': 'parana-sanpedro', 'river': 'Paraná', 'place': 'San Pedro', 'lat': -33.68, 'lon': -59.65},
    {'id': 'parana-zarate', 'river': 'Paraná', 'place': 'Zárate', 'lat': -34.09, 'lon': -59.02},
    {'id': 'paraguay-bahianegra', 'river': 'Paraguay', 'place': 'Bahía Negra', 'lat': -20.23, 'lon': -58.17},
    {'id': 'paraguay-concepcion', 'river': 'Paraguay', 'place': 'Concepción', 'lat': -23.41, 'lon': -57.45},
    {'id': 'paraguay-asuncion', 'river': 'Paraguay', 'place': 'Asunción', 'lat': -25.28, 'lon': -57.65},
    {'id': 'paraguay-formosa', 'river': 'Paraguay', 'place': 'Formosa · Alberdi', 'lat': -26.18, 'lon': -58.16},
    {'id': 'paraguay-pilar', 'river': 'Paraguay', 'place': 'Pilar', 'lat': -26.86, 'lon': -58.32},
    {'id': 'paraguay-humaita', 'river': 'Paraguay', 'place': 'Humaitá', 'lat': -27.07, 'lon': -58.52},
    {'id': 'bermejo-embarcacion', 'river': 'Bermejo', 'place': 'Embarcación', 'lat': -23.21, 'lon': -64.1},
    {'id': 'bermejo-elcolorado', 'river': 'Bermejo', 'place': 'El Colorado', 'lat': -26.31, 'lon': -59.37},
    {'id': 'uruguay-soberbio', 'river': 'Uruguay', 'place': 'El Soberbio', 'lat': -27.3, 'lon': -54.2},
    {'id': 'uruguay-albaposse', 'river': 'Uruguay', 'place': 'Alba Posse', 'lat': -27.57, 'lon': -54.68},
    {'id': 'uruguay-santotome', 'river': 'Uruguay', 'place': 'Santo Tomé', 'lat': -28.55, 'lon': -56.04},
    {'id': 'uruguay-libres', 'river': 'Uruguay', 'place': 'Paso de los Libres', 'lat': -29.71, 'lon': -57.08},
    {'id': 'uruguay-montecaseros', 'river': 'Uruguay', 'place': 'Monte Caseros', 'lat': -30.25, 'lon': -57.64},
    {'id': 'uruguay-concordia', 'river': 'Uruguay', 'place': 'Concordia · Salto', 'lat': -31.39, 'lon': -58.02},
    {'id': 'uruguay-colon', 'river': 'Uruguay', 'place': 'Colón', 'lat': -32.22, 'lon': -58.14},
    {'id': 'uruguay-cdeluruguay', 'river': 'Uruguay', 'place': 'Concepción del Uruguay', 'lat': -32.48, 'lon': -58.22},
    {'id': 'uruguay-fraybentos', 'river': 'Uruguay', 'place': 'Fray Bentos', 'lat': -33.12, 'lon': -58.31},
]

MODELS = 'ecmwf_ifs025,gfs025'
_CACHE = {}
TTL = 4 * 3600


def _cached(key, fn):
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    val = fn()
    _CACHE[key] = (time.monotonic(), val)
    return val


def load_normals():
    try:
        with open(NORMALS, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    pos = (len(xs) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _r(v, d=0):
    return None if v is None else round(v, d) if d else round(v)


# ───────────────────────────── 1. El Niño semanal ─────────────────────────────
NUM = re.compile(r'-?\d+\.\d')
REGIONS = ['nino12', 'nino3', 'nino34', 'nino4']
REGION_NAMES = {'nino12': 'Niño 1+2 · costero', 'nino3': 'Niño 3', 'nino34': 'Niño 3.4', 'nino4': 'Niño 4'}


def parse_cpc_weekly(text):
    """Líneas tipo ' 07OCT2026     22.5 1.3     26.5 1.2     28.2 1.6     29.6 1.0'.
    Las anomalías negativas vienen pegadas a la temperatura ('23.4-0.4')."""
    weeks = []
    for line in text.splitlines():
        m = re.match(r'\s*(\d{2})([A-Z]{3})(\d{4})\s+(.*)$', line)
        if not m:
            continue
        nums = [float(x) for x in NUM.findall(m.group(4))]
        if len(nums) != 8:
            continue
        mon = 'JANFEBMARAPRMAYJUNJULAUGSEPOCTNOVDEC'.index(m.group(2)) // 3 + 1
        row = {'week': f'{m.group(3)}-{mon:02d}-{m.group(1)}'}
        for i, k in enumerate(REGIONS):
            row[k] = {'sst': nums[2 * i], 'anom': nums[2 * i + 1]}
        weeks.append(row)
    return weeks


def phase(anom):
    if anom is None:
        return None
    if anom >= 2.0: return 'Niño muy fuerte'
    if anom >= 1.5: return 'Niño fuerte'
    if anom >= 1.0: return 'Niño moderado'
    if anom >= 0.5: return 'Niño débil'
    if anom > -0.5: return 'neutral'
    if anom > -1.0: return 'Niña débil'
    if anom > -1.5: return 'Niña moderada'
    return 'Niña fuerte'


def nino_weekly():
    r = c._get(CPC_WEEKLY)
    weeks = parse_cpc_weekly(r.text)
    if not weeks:
        raise ValueError('NOAA CPC no trajo semanas')
    last = weeks[-1]
    tail = weeks[-13:]
    return {
        'week': last['week'],
        'regions': [{'id': k, 'name': REGION_NAMES[k], 'sst': last[k]['sst'], 'anom': last[k]['anom'],
                     'phase': phase(last[k]['anom']),
                     'change_4w': round(last[k]['anom'] - weeks[-5][k]['anom'], 1) if len(weeks) >= 5 else None}
                    for k in REGIONS],
        'series': {'weeks': [w['week'] for w in tail], **{k: [w[k]['anom'] for w in tail] for k in ('nino12', 'nino34')}},
        'phase': phase(last['nino34']['anom']),
        'coastal': phase(last['nino12']['anom']),
        'source': CPC_WEEKLY, 'note': 'Anomalía semanal contra 1991-2020. El estado oficial se declara con el ONI trimestral.',
    }


# ───────────────────────────── 2. lluvia en cabeceras ─────────────────────────────
def _members(daily, var='precipitation_sum'):
    return {k: v for k, v in daily.items() if k == var or k.startswith(var + '_')}


def basin_rain(responses, basins=BASINS, normals=None, days=15):
    """responses: lista de respuestas Open-Meteo, en el mismo orden que los puntos de todas las cuencas."""
    out, i = [], 0
    normals = normals or {}
    for b in basins:
        group = responses[i:i + len(b['points'])]; i += len(b['points'])
        cols = None; per_point = []
        for resp in group:
            m = _members((resp or {}).get('daily') or {})
            per_point.append(m)
            cols = set(m) if cols is None else cols & set(m)
        totals = []; daily = []
        for col in sorted(cols or []):
            dd = []
            for j in range(days):
                vs = [m[col][j] for m in per_point if j < len(m[col]) and m[col][j] is not None]
                dd.append(sum(vs) / len(vs) if vs else None)
            daily.append(dd)
            vals = []
            for m in per_point:
                s = [v for v in m[col][:days] if v is not None]
                if len(s) >= days - 2:
                    vals.append(sum(s) * days / len(s))
            if vals:
                totals.append(sum(vals) / len(vals))
        if not totals:
            out.append({'id': b['id'], 'group': b.get('group'), 'name': b['name'], 'where': b['where'], 'travel': b['travel'], 'status': 'sin dato'})
            continue
        n = len(totals)
        norm = (normals.get(b['id']) or {})
        normal = norm.get('rain15_by_month', {}).get(str(date.today().month)) if norm else None
        med = quantile(totals, .5)
        times = ((group[0] or {}).get('daily') or {}).get('time') or []
        med_day = [_r(quantile([dd[j] for dd in daily if dd[j] is not None], .5), 1) for j in range(days)]
        cum, tot, center = 0.0, sum(v for v in med_day if v) or 0, None
        for j, v in enumerate(med_day):
            cum += v or 0
            if tot and cum >= tot / 2:
                center = j; break
        heavy = [j for j, v in enumerate(med_day) if v and v >= 10]
        r10 = max((sum(v or 0 for v in med_day[j:j + 10]) for j in range(max(1, days - 9))), default=None)
        out.append({'id': b['id'], 'group': b.get('group'), 'name': b['name'], 'where': b['where'], 'travel': b['travel'], 'status': 'recibido',
                    'daily_median': med_day, 'dates': times[:days], 'rain10_mm': _r(r10),
                    'rain_center': times[center] if center is not None and center < len(times) else None,
                    'rain_from': times[heavy[0]] if heavy and heavy[0] < len(times) else None,
                    'rain_to': times[heavy[-1]] if heavy and heavy[-1] < len(times) else None,
                    'members': n, 'median_mm': _r(med), 'p10_mm': _r(quantile(totals, .1)), 'p90_mm': _r(quantile(totals, .9)),
                    'p_ge50': round(100 * sum(t >= 50 for t in totals) / n), 'p_ge100': round(100 * sum(t >= 100 for t in totals) / n),
                    'p_ge200': round(100 * sum(t >= 200 for t in totals) / n),
                    'normal_mm': _r(normal), 'ratio': round(med / normal, 2) if normal else None})
    return out


def headwaters():
    pts = [p for b in BASINS for p in b['points']]
    params = {'latitude': ','.join(str(p[0]) for p in pts), 'longitude': ','.join(str(p[1]) for p in pts),
              'daily': 'precipitation_sum', 'models': MODELS, 'forecast_days': 16, 'timezone': 'America/Argentina/Buenos_Aires'}
    data = c._get(ENSEMBLE, params, timeout=40).json()
    data = data if isinstance(data, list) else [data]
    return {'days': 15, 'models': 'ECMWF IFS (51) + GFS (31)', 'basins': basin_rain(data, normals=load_normals().get('basins')),
            'source': ENSEMBLE}


# ───────────────────────────── 3. caudal de los ríos ─────────────────────────────
def river_level(pct):
    if pct is None: return None
    if pct < 10: return 'muy bajo'
    if pct < 30: return 'bajo'
    if pct <= 70: return 'normal'
    if pct <= 90: return 'alto'
    if pct <= 97: return 'muy alto'
    return 'extraordinario'


def percentile_in(value, q):
    """Ubica un valor entre los percentiles guardados {'p10','p25','p50','p75','p90','p97'} (interpolado)."""
    if value is None or not q:
        return None
    pts = sorted((int(k[1:]), v) for k, v in q.items() if k[:1] == 'p' and k[1:].isdigit() and v is not None)
    if q.get('min') is not None: pts.insert(0, (0, q['min']))
    if q.get('max') is not None: pts.append((100, q['max']))
    if value < pts[0][1]:
        return pts[0][0]
    for (p0, v0), (p1, v1) in zip(pts, pts[1:]):
        if value <= v1:
            return round(p0 + (p1 - p0) * ((value - v0) / (v1 - v0) if v1 > v0 else 1))
    return 99


def rivers_summary(responses, normals=None, today=None, past=7):
    today = today or date.today()
    normals = normals or {}
    out = []
    for st, resp in zip(STATIONS, responses):
        d = (resp or {}).get('daily') or {}
        t = d.get('time') or []
        q = d.get('river_discharge') or []
        med = d.get('river_discharge_median') or q
        hi = d.get('river_discharge_p75') or []
        if not t or not q:
            out.append({**_st(st), 'status': 'sin dato', 'height_record': (normals.get(st['id']) or {}).get('height_record')}); continue
        iso = today.isoformat()
        k = t.index(iso) if iso in t else min(past, len(t) - 1)
        now = q[k] if q[k] is not None else med[k]
        week_ago = q[max(0, k - 7)]
        fut = [(t[j], med[j]) for j in range(k + 1, len(t)) if med[j] is not None]
        peak = max(fut, key=lambda x: x[1]) if fut else None
        norm = (normals.get(st['id']) or {})
        clim = (norm.get('doy') or {}).get(f'{today.month:02d}-{(today.day // 5) * 5:02d}') if norm else None
        pct = percentile_in(now, clim)
        pk_clim = None
        if peak and norm:
            pd = date.fromisoformat(peak[0])
            pk_clim = (norm.get('doy') or {}).get(f'{pd.month:02d}-{(pd.day // 5) * 5:02d}')
        pk_pct = percentile_in(peak[1], pk_clim) if peak else None
        out.append({**_st(st), 'status': 'recibido', 'date': t[k], 'discharge': _r(now), 'change_7d_pct': _r(100 * (now - week_ago) / week_ago) if week_ago else None,
                    'normal': _r((clim or {}).get('p50')), 'ratio': round(now / clim['p50'], 2) if clim and clim.get('p50') else None,
                    'percentile': pct, 'level': river_level(pct),
                    'peak_date': peak[0] if peak else None, 'peak': _r(peak[1]) if peak else None,
                    'peak_percentile': pk_pct, 'peak_level': river_level(pk_pct),
                    'danger': danger(now, norm.get('return_periods')), 'peak_danger': danger(peak[1] if peak else None, norm.get('return_periods')),
                    'thresholds': norm.get('return_periods'), 'height_record': norm.get('height_record'),
                    'series': {'dates': t, 'discharge': [_r(v) for v in q], 'median': [_r(v) for v in med], 'p75': [_r(v) for v in hi]}})
    return out


def _st(st):
    return {'id': st['id'], 'river': st['river'], 'place': st['place']}


def rivers():
    normals = load_normals().get('stations') or {}
    cells = [(normals.get(s['id'], {}).get('lat', s['lat']), normals.get(s['id'], {}).get('lon', s['lon'])) for s in STATIONS]
    params = {'latitude': ','.join(str(a) for a, _ in cells), 'longitude': ','.join(str(b) for _, b in cells),
              'daily': 'river_discharge,river_discharge_median,river_discharge_p75', 'past_days': 7, 'forecast_days': 30}
    data = c._get(FLOOD, params, timeout=40).json()
    data = data if isinstance(data, list) else [data]
    allnorm = load_normals()
    st_out = rivers_summary(data, normals)
    ina = None
    try:
        ina = ina_all()
    except Exception:
        pass
    st_out = merge_ina(st_out, ina)
    return {'stations': st_out, 'normals': bool(normals), 'travel': travel(st_out, allnorm), 'actions': ACTIONS,
            'ina_forecast_issued': ((ina or {}).get('forecast') or {}).get('issued'),
            'lags_period': allnorm.get('lags_period'), 'source': FLOOD,
            'note': 'Caudal simulado por GloFAS (Copernicus) en grilla de ~5 km. Se compara con su propia serie 2001-2020; '
                    'para alturas oficiales en puertos, ver Prefectura Naval e INA.'}


# ───────────────────────────── 4. tiempos de traslado y peligro ─────────────────────────────
# Tramos encadenados del cauce principal: la onda de crecida baja de una estación a la siguiente.
CHAINS = [
    {'id': 'iguazu-parana', 'name': 'Del Iguazú al Paraná', 'stations': ['iguazu-andresito', 'iguazu-cataratas', 'parana-eldorado', 'parana-posadas', 'parana-ituzaingo', 'parana-corrientes', 'parana-bellavista', 'parana-goya', 'parana-reconquista', 'parana-esquina', 'parana-lapaz', 'parana-santafe', 'parana-diamante', 'parana-rosario', 'parana-sannicolas', 'parana-sanpedro', 'parana-zarate']},
    {'id': 'paraguay', 'name': 'Río Paraguay', 'stations': ['paraguay-bahianegra', 'paraguay-concepcion', 'paraguay-asuncion', 'paraguay-formosa', 'paraguay-pilar', 'paraguay-humaita', 'parana-corrientes']},
    {'id': 'bermejo', 'name': 'Río Bermejo', 'stations': ['bermejo-embarcacion', 'bermejo-elcolorado', 'paraguay-humaita']},
    {'id': 'uruguay', 'name': 'Río Uruguay', 'stations': ['uruguay-soberbio', 'uruguay-albaposse', 'uruguay-santotome', 'uruguay-libres', 'uruguay-montecaseros', 'uruguay-concordia', 'uruguay-colon', 'uruguay-cdeluruguay', 'uruguay-fraybentos']},
]

LEVELS = ['Normal', 'Atención', 'Alerta', 'Peligro']
ACTIONS = {
    'Normal': ['Seguir el pronóstico semanal del río y la lluvia en las cabeceras.'],
    'Atención': ['Mirar el pronóstico todos los días.', 'Identificar lomas, corrales y potreros altos para la hacienda.',
                 'Revisar alambrados, accesos y alcantarillas.'],
    'Alerta': ['Sacar la hacienda de bajos, islas y costas hacia zonas altas.', 'Asegurar agua de bebida segura, forraje y combustible.',
               'Adelantar traslados o ventas si los caminos pueden cortarse.', 'Reforzar sanidad: pietín, mosca, parásitos.'],
    'Peligro': ['Evacuar hacienda y personas de zonas inundables con tiempo.', 'Seguir a Defensa Civil y Prefectura; no cruzar caminos anegados.',
                'Mover maquinaria, insumos y documentación a lugares altos.'],
}


def danger(q, rp):
    """Nivel según las crecidas de 2, 5 y 20 años (los umbrales que usa GloFAS)."""
    if q is None or not rp:
        return None
    if rp.get('q20') and q >= rp['q20']: return 'Peligro'
    if rp.get('q5') and q >= rp['q5']: return 'Alerta'
    if rp.get('q2') and q >= rp['q2']: return 'Atención'
    return 'Normal'


def _add_days(iso, days):
    return (date.fromisoformat(iso) + timedelta(days=round(days))).isoformat()


def travel(stations_out, normals):
    """Tiempo acumulado por tramo (de las normales) y llegada estimada del pico de cabecera."""
    by = {s['id']: s for s in stations_out}
    lags = (normals or {}).get('lags') or {}
    out = []
    for ch in CHAINS:
        ids = ch['stations']; acc = 0.0; rows = []
        head = by.get(ids[0]) or {}
        ok = True
        for i, sid in enumerate(ids):
            if i:
                lg = lags.get(f'{ids[i - 1]}>{sid}')
                if not lg:
                    ok = False
                acc += (lg or {}).get('days', 0)
            st = by.get(sid) or {}
            lg = lags.get(f'{ids[i - 1]}>{sid}') if i else None
            rows.append({'id': sid, 'place': st.get('place') or sid, 'river': st.get('river'),
                         'days_from_head': round(acc, 1) if ok else None,
                         'leg_days': (lg or {}).get('days'), 'leg_corr': (lg or {}).get('corr'),
                         'arrival': _add_days(head['peak_date'], acc) if ok and head.get('peak_date') else None,
                         'glofas_peak_date': st.get('peak_date'), 'level_now': st.get('danger'), 'level_peak': st.get('peak_danger')})
        out.append({'id': ch['id'], 'name': ch['name'], 'head_peak': head.get('peak_date'), 'head_level': head.get('peak_danger'), 'rows': rows})
    return out


# ───────────────────────────── 5. represas de Brasil (ONS, medido) ─────────────────────────────
ONS_CSV = 'https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_di/DADOS_HIDROLOGICOS_RES_{year}.csv'
DAMS = [
    {'id': 'salto-caxias', 'outlet': 'iguazu-cataratas', 'match': ['SALTO CAXIAS'], 'name': 'Salto Caxias', 'river': 'Iguazú', 'note': 'última gran represa antes de Cataratas · ~1 día'},
    {'id': 'itaipu', 'outlet': 'parana-posadas', 'match': ['ITAIPU'], 'name': 'Itaipú', 'river': 'Paraná', 'note': 'lo que suelta llega a Posadas en ~1 a 2 días'},
    {'id': 'porto-primavera', 'outlet': 'parana-posadas', 'match': ['PORTO PRIMAVERA', 'ENG SERGIO MOTTA'], 'name': 'Porto Primavera', 'river': 'Paraná', 'note': 'Alto Paraná, antes de Itaipú'},
    {'id': 'foz-chapeco', 'outlet': 'uruguay-soberbio', 'match': ['FOZ DO CHAPECO'], 'name': 'Foz do Chapecó', 'river': 'Uruguay', 'note': 'Alto Uruguay · a Paso de los Libres en ~3 a 5 días'},
    {'id': 'ita', 'outlet': 'uruguay-soberbio', 'match': ['ITA'], 'exact': True, 'name': 'Itá', 'river': 'Uruguay', 'note': 'Alto Uruguay, Santa Catarina'},
]


def _norm(txt):
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFD', str(txt).upper()) if unicodedata.category(ch) != 'Mn').strip()


def dam_for(name):
    n = _norm(name)
    for d in DAMS:
        for m in d['match']:
            if (n == m) if d.get('exact') else (m in n):
                return d['id']
    return None


def parse_ons(lines):
    """CSV del ONS (separador ';') → {dam_id: [(fecha, afluente, defluente)]}. Busca las columnas por nombre."""
    it = iter(lines)
    header = next(it, '')
    sep = ';' if header.count(';') >= header.count(',') else ','
    cols = [h.strip().strip('"').lower() for h in header.split(sep)]
    def col(*keys):
        for i, h in enumerate(cols):
            if all(k in h for k in keys):
                return i
        return None
    i_name, i_date = col('nom_reservatorio') if col('nom_reservatorio') is not None else col('reservatorio'), col('din_instante') if col('din_instante') is not None else col('data')
    i_in, i_out = col('vazaoafluente'), col('vazaodefluente')
    if None in (i_name, i_date, i_out):
        raise ValueError('El ONS cambió el formato del archivo')
    num = lambda x: float(x.replace(',', '.')) if x not in ('', None) else None
    out = {}
    for line in it:
        parts = [p.strip().strip('"') for p in line.split(sep)]
        if len(parts) <= max(i for i in (i_name, i_date, i_out, i_in) if i is not None):
            continue
        did = dam_for(parts[i_name])
        if not did:
            continue
        try:
            row = (parts[i_date][:10], num(parts[i_in]) if i_in is not None else None, num(parts[i_out]))
        except ValueError:
            continue
        out.setdefault(did, []).append(row)
    for k in out:
        out[k].sort()
    return out


def dams_summary(series, normals=None):
    normals = normals or {}
    res = []
    for d in DAMS:
        rows = [r for r in series.get(d['id'], []) if r[2] is not None]
        base = {'id': d['id'], 'name': d['name'], 'river': d['river'], 'note': d['note'], 'outlet': d.get('outlet')}
        if not rows:
            res.append({**base, 'status': 'sin dato'}); continue
        day, qin, qout = rows[-1]
        wk = [r for r in rows if r[0] <= (date.fromisoformat(day) - timedelta(days=7)).isoformat()]
        dd = date.fromisoformat(day)
        clim = ((normals.get(d['id']) or {}).get('doy') or {}).get(f'{dd.month:02d}-{(dd.day // 5) * 5:02d}')
        pct = percentile_in(qout, clim)
        res.append({**base, 'status': 'recibido', 'date': day, 'inflow': _r(qin), 'outflow': _r(qout),
                    'change_7d_pct': _r(100 * (qout - wk[-1][2]) / wk[-1][2]) if wk and wk[-1][2] else None,
                    'normal': _r((clim or {}).get('p50')), 'ratio': round(qout / clim['p50'], 2) if clim and clim.get('p50') else None,
                    'percentile': pct, 'level': river_level(pct),
                    'series': {'dates': [r[0] for r in rows[-45:]], 'outflow': [_r(r[2]) for r in rows[-45:]]}})
    return res


def dams():
    year = c._now().year
    r = c.SESSION.get(ONS_CSV.format(year=year), timeout=45, stream=True)
    if r.status_code == 404 and c._now().month == 1:
        r = c.SESSION.get(ONS_CSV.format(year=year - 1), timeout=45, stream=True)
    r.raise_for_status()
    r.encoding = r.encoding or 'utf-8'
    series = parse_ons(r.iter_lines(decode_unicode=True))
    return {'dams': dams_summary(series, load_normals().get('dams')), 'source': 'https://dados.ons.org.br/dataset/dados-hidrologicos-res',
            'note': 'Caudal medido y consolidado por el ONS (Brasil), en m³/s. Afluente: lo que entra; defluente: lo que la represa suelta río abajo.'}


# ───────────────────────────── 6. alerta temprana por lluvia en cabeceras ─────────────────────────────
ORDER = ['Normal', 'Atención', 'Alerta', 'Peligro']


def rain_level(b):
    """Nivel por la lluvia pronosticada en la cuenca (reglas declaradas, no un modelo opaco)."""
    if b.get('status') != 'recibido':
        return None, []
    why, lvl = [], 'Normal'
    p100, p200, ratio = b.get('p_ge100') or 0, b.get('p_ge200') or 0, b.get('ratio')
    def up(to, txt):
        nonlocal lvl
        if ORDER.index(to) > ORDER.index(lvl):
            lvl = to
        why.append(txt)
    if p200 >= 50: up('Peligro', f'{p200} % de chances de superar 200 mm en 15 días')
    elif p200 >= 25 or p100 >= 70: up('Alerta', f'{p100} % de chances de superar 100 mm' + (f' y {p200} % de superar 200 mm' if p200 else ''))
    elif p100 >= 40: up('Atención', f'{p100} % de chances de superar 100 mm en 15 días')
    if ratio is not None and ratio >= 2: up('Alerta', f'lluvia esperada {ratio:.1f} veces la normal de la época')
    elif ratio is not None and ratio >= 1.5: up('Atención', f'lluvia esperada {ratio:.1f} veces la normal de la época')
    return lvl, why


def nf_m(v):
    return '—' if v is None else f'{v:.2f}'.replace('.', ',')


def _bump(lvl):
    return ORDER[min(len(ORDER) - 1, ORDER.index(lvl) + 1)]


def _span(iso, lo, hi):
    if not iso:
        return None
    return [_add_days(iso, lo), _add_days(iso, hi)]


def early_warning(basins, stations, dams_list=None, normals=None):
    """Para cada cabecera: nivel, motivos y ventana de llegada a cada localidad aguas abajo."""
    st = {s['id']: s for s in stations or []}
    lags = (normals or {}).get('lags') or {}
    dams_list = dams_list or []
    out = []
    for b in basins or []:
        cfg = next((x for x in BASINS if x['id'] == b['id']), None)
        lvl, why = rain_level(b)
        if lvl is None or not cfg:
            continue
        outlet = st.get(cfg['outlet']) or {}
        # agravantes: río de salida ya alto o represa aguas arriba soltando mucho (sube a lo sumo un escalón)
        bump = []
        il = (outlet.get('ina') or {}).get('level')
        if il in ('Atención', 'Alerta', 'Evacuación'):
            bump.append(f"el río en {outlet.get('place')} ya está en {il.lower()} ({nf_m((outlet.get('ina') or {}).get('height'))} m)")
        elif outlet.get('level') in ('alto', 'muy alto', 'extraordinario'):
            bump.append(f"el río en {outlet.get('place')} ya viene {outlet['level']}: el suelo y el cauce están cargados")
        for d in dams_list:
            if d.get('outlet') == cfg['outlet'] and d.get('level') in ('muy alto', 'extraordinario') and cfg['response'][0] < 20:
                bump.append(f"la represa {d['name']} ya suelta un caudal {d['level']}"); break
        if lvl != 'Normal' and bump:
            lvl = _bump(lvl); why.extend(bump)
        # cálculo lluvia → crecida (20 años): cuánto podría subir el río de salida con la lluvia pronosticada
        pred = None
        rr = ((normals or {}).get('rain_rise') or {}).get(cfg['outlet']) or {}
        r10 = b.get('rain10_mm')
        ina = outlet.get('ina') or {}
        if r10:
            hr = rr.get('height'); qr = rr.get('discharge')
            if hr and ina.get('height') is not None:
                rise = hr['per10mm'] * r10 / 10
                ph = round(ina['height'] + rise, 2)
                plv = height_level(ph, {'alert': ina.get('alert'), 'evac': ina.get('evac')}, outlet.get('river'))
                pred = {'kind': 'altura', 'place': outlet.get('place'), 'rain10_mm': r10, 'rise_m': round(rise, 2), 'from_m': ina['height'], 'to_m': ph,
                        'alert_m': ina.get('alert'), 'evac_m': ina.get('evac'), 'level': plv, 'per10mm_m': hr['per10mm'], 'r': hr['r'], 'cases': hr['cases'],
                        'rain_alert_mm': hr.get('rain_alert_mm'), 'rain_evac_mm': hr.get('rain_evac_mm')}
            elif qr and outlet.get('discharge') is not None:
                rise = qr['per10mm'] * r10 / 10
                pq = round(outlet['discharge'] + rise)
                rp = outlet.get('thresholds')
                pred = {'kind': 'caudal', 'place': outlet.get('place'), 'rain10_mm': r10, 'rise_q': round(rise), 'from_q': outlet['discharge'], 'to_q': pq,
                        'level': danger(pq, rp), 'per10mm_q': qr['per10mm'], 'r': qr['r'], 'cases': qr['cases'],
                        'rain_alert_mm': qr.get('rain_q5_mm'), 'rain_evac_mm': qr.get('rain_q20_mm')}
            if pred and pred.get('level'):
                target = {'Evacuación': 'Peligro'}.get(pred['level'], pred['level'])
                if target in ORDER and ORDER.index(target) > ORDER.index(lvl):
                    lvl = target
                    why.append(f"el cálculo lluvia-crecida de 20 años indica nivel {pred['level'].lower()} en {pred['place']}")
        start = b.get('rain_center') or b.get('rain_from')
        lo, hi = cfg['response']
        arrivals = []
        if lvl != 'Normal' and start:
            arrivals.append({'place': outlet.get('place') or cfg['outlet'], 'river': outlet.get('river'), 'window': _span(start, lo, hi)})
            chain = next((ch['stations'] for ch in CHAINS if cfg['outlet'] in ch['stations']), [])
            acc = 0.0
            if chain:
                for u, dn in zip(chain[chain.index(cfg['outlet']):], chain[chain.index(cfg['outlet']) + 1:]):
                    lg = lags.get(f'{u}>{dn}')
                    if not lg:
                        break
                    acc += lg['days']
                    s2 = st.get(dn) or {}
                    arrivals.append({'place': s2.get('place') or dn, 'river': s2.get('river'), 'window': _span(start, lo + acc, hi + acc)})
        out.append({'basin': b['id'], 'group': cfg.get('group'), 'name': b['name'], 'where': b['where'], 'level': lvl, 'why': why, 'prediction': pred,
                    'rain_from': b.get('rain_from'), 'rain_to': b.get('rain_to'), 'median_mm': b.get('median_mm'),
                    'p_ge100': b.get('p_ge100'), 'arrivals': arrivals, 'actions': ACTIONS.get(lvl, [])})
    out.sort(key=lambda a: -ORDER.index(a['level']))
    return out


# ───────────────────────────── 7. mapas satelitales (NASA GIBS, abiertos) ─────────────────────────────
GIBS_WMS = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi'
PLATA_BBOX = (-66.0, -35.0, -44.0, -14.0)      # lon/lat: toda la Cuenca del Plata
PACIFIC_BBOX = (-160.0, -30.0, -70.0, 30.0)     # como el mapa OISST de NOAA


def gibs_url(layer, bbox, day, width, height, fmt='image/png'):
    from urllib.parse import urlencode
    q = {'SERVICE': 'WMS', 'REQUEST': 'GetMap', 'VERSION': '1.1.1', 'LAYERS': layer, 'STYLES': '', 'SRS': 'EPSG:4326',
         'BBOX': ','.join(f'{v:g}' for v in bbox), 'WIDTH': width, 'HEIGHT': height, 'FORMAT': fmt, 'TRANSPARENT': 'TRUE'}
    if day:
        q['TIME'] = day
    return f'{GIBS_WMS}?{urlencode(q)}'


def basin_bbox(basin_id, pad=1.2):
    b = next((x for x in BASINS if x['id'] == basin_id), None)
    if not b:
        return PLATA_BBOX
    lats = [p[0] for p in b['points']]; lons = [p[1] for p in b['points']]
    x0, x1, y0, y1 = min(lons) - pad, max(lons) + pad, min(lats) - pad, max(lats) + pad
    # proporción 3:2 para la foto
    w, h = x1 - x0, y1 - y0
    if w < 1.5 * h:
        cx = (x0 + x1) / 2; x0, x1 = cx - 0.75 * h, cx + 0.75 * h
    else:
        cy = (y0 + y1) / 2; y0, y1 = cy - w / 3, cy + w / 3
    return (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))


def maps(alerts=None, today=None):
    today = today or c._now().date()
    y1 = (today - timedelta(days=1)).isoformat(); y2 = (today - timedelta(days=2)).isoformat()
    worst = next((a for a in (alerts or []) if a.get('level') not in (None, 'Normal')), None)
    zone_bbox = basin_bbox(worst['basin']) if worst else PLATA_BBOX
    zone_name = worst['name'] if worst else 'Cuenca del Plata'
    return {
        'sst': {'title': 'Anomalía de temperatura del mar · Pacífico', 'date': y2, 'bbox': PACIFIC_BBOX,
                'layers': [gibs_url('GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies', PACIFIC_BBOX, y2, 900, 600),
                           gibs_url('GHRSST_L4_MUR25_Sea_Surface_Temperature_Anomalies', PACIFIC_BBOX, y2, 900, 600)],
                'overlay': gibs_url('Coastlines_15m', PACIFIC_BBOX, None, 900, 600),
                'caption': 'GHRSST MUR (NASA JPL) vía NASA GIBS. Rojo: mar más cálido que lo normal; azul: más frío. La lengua cálida sobre el ecuador es El Niño; la mancha junto a Perú, el Niño costero.'},
        'zone': {'title': f'Imagen satelital del día · {zone_name}', 'date': y1, 'bbox': zone_bbox,
                 'layers': [gibs_url('VIIRS_SNPP_CorrectedReflectance_TrueColor', zone_bbox, y1, 900, 600, 'image/jpeg'),
                            gibs_url('MODIS_Terra_CorrectedReflectance_TrueColor', zone_bbox, y1, 900, 600, 'image/jpeg')],
                 'overlay': gibs_url('Coastlines_15m', zone_bbox, None, 900, 600),
                 'caption': 'VIIRS (Suomi NPP) color real, NASA GIBS. Muestra nubes y ríos desbordados cuando el cielo está despejado; resolución ~250-375 m.'},
        'rain': {'title': 'Lluvia satelital sobre la Cuenca del Plata', 'date': y1, 'bbox': PLATA_BBOX,
                 'layers': [gibs_url('IMERG_Precipitation_Rate', PLATA_BBOX, y1, 840, 800)],
                 'base': gibs_url('VIIRS_SNPP_CorrectedReflectance_TrueColor', PLATA_BBOX, y1, 840, 800, 'image/jpeg'),
                 'overlay': gibs_url('Coastlines_15m', PLATA_BBOX, None, 840, 800),
                 'caption': 'GPM IMERG (NASA) vía GIBS: intensidad de lluvia estimada por satélite, sobre la imagen del día.'},
    }


# ───────────────────────────── 8. INA: alturas, niveles oficiales y pronóstico ─────────────────────────────
INA = 'https://alerta.ina.gob.ar/pub/datos'
# Localidad → sitecode INA (escalas de Prefectura). Niveles oficiales (m) leídos de INA el 13/10/2026;
# se refrescan en vivo desde /estaciones y estos quedan sólo de respaldo.
INA_SITES = {
    'iguazu-andresito': (8, 10.5, 13.5, 0.16), 'iguazu-cataratas': (9, 25, 28, 9.4), 'parana-eldorado': (11, 23, 25, 7.5),
    'parana-posadas': (14, 11, 12, 9.8), 'parana-ituzaingo': (15, 3.5, 4, 0.81), 'parana-corrientes': (19, 6.5, 7, 1.83),
    'parana-bellavista': (22, 6, 6.4, 3), 'parana-goya': (23, 5.2, 5.7, 2.23), 'parana-reconquista': (24, 5.1, 5.3, 2.18),
    'parana-esquina': (25, 5, 5.4, 2.2), 'parana-lapaz': (26, 5.8, 6.15, 2.38), 'parana-santafe': (29, 4.7, 5, 1.61),
    'parana-diamante': (31, 5.3, 5.5, 2.4), 'parana-rosario': (34, 5, 5.25, 1.64), 'parana-sannicolas': (36, 4.2, 5, 1.35),
    'parana-sanpedro': (38, 3.4, 3.6, 0.84), 'parana-zarate': (40, 2, 2.2, 0.25),
    'paraguay-asuncion': (55, 5.35, 6, 1.4), 'paraguay-formosa': (57, 7.8, 8.3, 1.6), 'paraguay-humaita': (58, 6.5, 7, None),
    'uruguay-soberbio': (61, None, None, None), 'uruguay-santotome': (68, 11.5, 12.5, 1.32), 'uruguay-libres': (72, 7.5, 8.5, 0.9),
    'uruguay-montecaseros': (74, 7.5, 8.5, 0.8), 'uruguay-concordia': (79, 11, 12.5, 0.88), 'uruguay-colon': (80, 7.1, 7.9, 0.9),
    'uruguay-cdeluruguay': (81, 5.3, 6.3, 0.8),
}
INA_NAMES = {'iguazu-cataratas': 'escala Puerto Iguazú (río Paraná)', 'paraguay-asuncion': 'escala Puerto Pilcomayo (frente a Asunción)',
             'paraguay-humaita': 'escala Puerto Bermejo', 'parana-santafe': 'escala Paraná'}
INA_PRONO_CAL = 289          # "tabprono_central": pronóstico oficial del INA para el Paraná (Corrientes a Rosario)
ATTENTION_M = {'Iguazú': 2.0, 'Uruguay': 2.0}   # metros antes del nivel de alerta para pasar a Atención (resto: 1 m)


def ina_url(endpoint, **params):
    """La API del INA lee los parámetros con '&' después del recurso (como en su documentación)."""
    from urllib.parse import urlencode
    return f'{INA}/{endpoint}&{urlencode(params)}'


def ina_get(endpoint, timeout=20, **params):
    r = c.SESSION.get(ina_url(endpoint, **params), timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict) and j.get('mensaje') and 'data' not in j:
        raise ValueError(f"INA: {j['mensaje']}")
    return j


def ina_levels():
    """Niveles oficiales vigentes por sitecode (alerta, evacuación, aguas bajas). Respaldo: la tabla fija."""
    out = {sid: {'alert': a, 'evac': e, 'low': lw} for sid, (sc, a, e, lw) in INA_SITES.items()}
    try:
        rows = ina_get('estaciones', norte=-20, sur=-34.5, este=-53.5, oeste=-61, format='json', timeout=25)
        rows = rows.get('data', rows) if isinstance(rows, dict) else rows
        by = {int(r['sitecode']): r for r in rows if str(r.get('sitecode', '')).isdigit()}
        for sid, (sc, *_rest) in INA_SITES.items():
            r = by.get(sc)
            if r:
                out[sid] = {'alert': r.get('nivel_de_alerta'), 'evac': r.get('nivel_de_evacuacion'), 'low': r.get('nivel_de_aguas_bajas')}
    except Exception:
        pass
    return out


def ina_heights(sid, today=None, days=15):
    today = today or c._now().date()
    sc = INA_SITES[sid][0]
    j = ina_get('datos', timeStart=(today - timedelta(days=days)).isoformat(), timeEnd=(today + timedelta(days=1)).isoformat(),
                siteCode=sc, varId=2, format='json')
    rows = sorted((str(r['timestart'])[:10], float(r['valor'])) for r in j.get('data') or [] if r.get('valor') is not None)
    by_day = {}
    for d, v in rows:
        by_day[d] = v                       # último valor del día
    return sorted(by_day.items())


def ina_forecast(today=None):
    """Pronóstico oficial del INA (tabprono): por localidad, fechas con mínimo, central y máximo."""
    today = today or c._now().date()
    meta = ina_get('seriesProno', varId=2, calId=INA_PRONO_CAL, format='json')
    meta = meta.get('data', meta) if isinstance(meta, dict) else meta
    sites = {int(m['sitecode']): m for m in meta if str(m.get('sitecode', '')).isdigit()}
    issued = max((str(m.get('forecastdate', ''))[:10] for m in sites.values()), default=None)
    inv = {v[0]: k for k, v in INA_SITES.items()}
    out = {}
    def one(sc):
        j = ina_get('datosProno', timeStart=(issued or today.isoformat()), timeEnd=(today + timedelta(days=45)).isoformat(),
                    siteCode=sc, varId=2, calId=INA_PRONO_CAL, format='json')
        by = {}
        for r in j.get('data') or []:
            if r.get('valor') is not None:
                by.setdefault(str(r['timestart'])[:10], []).append(float(r['valor']))
        return [{'date': d, 'min': min(v), 'central': sorted(v)[len(v) // 2], 'max': max(v)} for d, v in sorted(by.items()) if d >= today.isoformat()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {inv[sc]: pool.submit(one, sc) for sc in sites if sc in inv}
        for sid, f in jobs.items():
            try:
                out[sid] = f.result()
            except Exception:
                pass
    return {'issued': issued, 'by_site': out, 'model': 'INA · pronóstico tabprono'}


def height_level(h, lv, river=None):
    """Nivel por altura contra los niveles oficiales: Evacuación, Alerta, Atención (1-2 m antes) o Normal."""
    if h is None or not lv or lv.get('alert') is None:
        return None
    if lv.get('evac') is not None and h >= lv['evac']: return 'Evacuación'
    if h >= lv['alert']: return 'Alerta'
    if h >= lv['alert'] - ATTENTION_M.get(river, 1.0): return 'Atención'
    return 'Normal'


def ina_all(today=None):
    today = today or c._now().date()
    levels = ina_levels()
    heights = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {sid: pool.submit(ina_heights, sid, today) for sid in INA_SITES}
        for sid, f in jobs.items():
            try:
                heights[sid] = f.result()
            except Exception:
                heights[sid] = []
    try:
        prono = ina_forecast(today)
    except Exception:
        prono = {'issued': None, 'by_site': {}}
    return {'levels': levels, 'heights': heights, 'forecast': prono}


def merge_ina(stations, ina):
    """Suma a cada localidad la altura del INA, los niveles oficiales, el nivel y el pronóstico oficial."""
    if not ina:
        return stations
    for s in stations:
        sid = s['id']
        if sid not in INA_SITES:
            continue
        hs = ina['heights'].get(sid) or []
        lv = ina['levels'].get(sid) or {}
        fc = (ina.get('forecast') or {}).get('by_site', {}).get(sid) or []
        h = hs[-1][1] if hs else None
        wk = [v for d, v in hs if d <= (date.fromisoformat(hs[-1][0]) - timedelta(days=7)).isoformat()] if hs else []
        fmax = max((x['max'] for x in fc), default=None)
        s['ina'] = {'site': INA_SITES[sid][0], 'gauge': INA_NAMES.get(sid), 'height': h, 'date': hs[-1][0] if hs else None,
                    'change_7d': round(h - wk[-1], 2) if h is not None and wk else None,
                    'alert': lv.get('alert'), 'evac': lv.get('evac'), 'low': lv.get('low'),
                    'to_alert': round(lv['alert'] - h, 2) if h is not None and lv.get('alert') is not None else None,
                    'level': height_level(h, lv, s.get('river')),
                    'forecast': fc, 'forecast_level': height_level(fmax, lv, s.get('river')),
                    'series': [{'date': d, 'h': v} for d, v in hs]}
        if s['ina']['level']:
            s['danger'] = s['ina']['level']; s['danger_source'] = 'INA'
        if s['ina']['forecast_level']:
            s['peak_danger'] = s['ina']['forecast_level']
    return stations


# ───────────────────────────── todo junto ─────────────────────────────
def analyze():
    def run():
        out = {'nino': None, 'headwaters': None, 'rivers': None, 'dams': None, 'errors': {}}
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {'nino': pool.submit(nino_weekly), 'headwaters': pool.submit(headwaters), 'rivers': pool.submit(rivers), 'dams': pool.submit(dams)}
            for k, f in jobs.items():
                try:
                    out[k] = f.result()
                except Exception as e:
                    out['errors'][k] = type(e).__name__
        try:
            out['alerts'] = early_warning((out['headwaters'] or {}).get('basins'), (out['rivers'] or {}).get('stations'),
                                          (out['dams'] or {}).get('dams'), load_normals()) if out['headwaters'] else None
        except Exception as e:
            out['alerts'] = None; out['errors']['alerts'] = type(e).__name__
        out['maps'] = maps(out.get('alerts'))
        ok = any(out[k] for k in ('nino', 'headwaters', 'rivers', 'dams'))
        return c.envelope(out, 'multi', 'Cuenca del Plata: El Niño, lluvia en cabeceras y ríos',
                          'NOAA CPC · ECMWF · NOAA GFS · Copernicus GloFAS (vía Open-Meteo) · ONS Brasil',
                          'recibido' if ok else 'sin dato', None if ok else 'Ninguna fuente respondió')
    res = _cached('cuenca', run)
    if res['status'] != 'recibido':
        _CACHE.pop('cuenca', None)   # no se guarda un fallo
    return res
