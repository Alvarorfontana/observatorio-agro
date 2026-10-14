"""enso_chain v1.0 — la cadena de El Niño, del Pacífico al lote.

Pasos medidos (todos abiertos, sin clave):
  1. Alisios         · NOAA CPC, índices de viento a 850 hPa (Pacífico oeste, central y este), anomalía estandarizada.
  2. Calor bajo el mar· NOAA CPC, anomalía de temperatura de 0-300 m en el Pacífico ecuatorial (180°-100°O).
  3. Superficie       · NOAA PSL, Niño 3.4, Niño 1+2 y ONI.
  4. Atmósfera        · NOAA PSL, SOI y MEI v2; NOAA CPC, radiación de onda larga (OLR, nubosidad) 160°E-160°O.
  5. El lote          · lluvia de octubre a marzo en cada temporada desde 1991 (ERA5) comparada según fase ENSO (ONI).
"""
import re
from concurrent.futures import ThreadPoolExecutor
from statistics import mean, median

import research_connectors as c
import climate_indices as ci

CPC = 'https://www.cpc.ncep.noaa.gov/data/indices/'
HEAT = 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ocean/index/heat_content_index.txt'
MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def parse_cpc(text):
    """Archivos de índices CPC (cpac850, olr…): secciones ORIGINAL / ANOMALY / STANDARDIZED, ancho fijo de 6."""
    sections, cur = {}, 'ORIGINAL'
    for line in text.splitlines():
        u = line.upper()
        if 'DATA' in u and not re.match(r'^\s*\d{4}', line):
            words = [w for w in re.findall(r'[A-Z]+', u) if w != 'DATA']
            if words:
                cur = words[0]
            continue
        m = re.match(r'^(\d{4})(.*)$', line.rstrip())
        if not m:
            continue
        y, rest = int(m.group(1)), m.group(2)
        vals = [rest[i:i + 6] for i in range(0, 72, 6)]
        for mi, v in enumerate(vals, start=1):
            try:
                f = float(v)
            except ValueError:
                continue
            if f > -999:
                sections.setdefault(cur, []).append((y, mi, f))
    return sections


def parse_heat(text):
    rows = []
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 5 and p[0].isdigit() and p[1].isdigit():
            try:
                rows.append((int(p[0]), int(p[1]), float(p[4])))   # 180°O-100°O
            except ValueError:
                pass
    return rows


def records(rows, higher_is_nino=True):
    """Máximo y mínimo histórico de la serie y desde cuándo no se veía un valor como el actual."""
    if not rows:
        return None
    hi = max(rows, key=lambda r: r[2]); lo = min(rows, key=lambda r: r[2])
    y, m, v = rows[-1]
    since = None
    for yy, mm, vv in reversed(rows[:-1]):
        if (vv >= v if v >= 0 else vv <= v):
            since = f'{MONTHS[mm - 1]} {yy}'; break
    ext = 'más alto' if v >= 0 else 'más bajo'
    return {'max': {'value': round(hi[2], 2), 'date': f'{MONTHS[hi[1] - 1]} {hi[0]}'},
            'min': {'value': round(lo[2], 2), 'date': f'{MONTHS[lo[1] - 1]} {lo[0]}'},
            'from': f'{rows[0][0]}', 'since': since,
            'since_text': (f'el valor {ext} desde {since}' if since else f'el valor {ext} de toda la serie (desde {rows[0][0]})')}


def _last(rows, n=12):
    return [{'period': f'{MONTHS[m - 1]} {y}', 'value': round(v, 2)} for y, m, v in rows[-n:]]


def _cpc_index(name, prefer=('STANDARDIZED', 'ANOMALY')):
    sec = parse_cpc(c._get(CPC + name, timeout=25).text)
    for k in prefer:
        if sec.get(k):
            return k, sec[k]
    raise ValueError(f'{name}: sin datos')


def psl_series(key):
    """Serie mensual completa de un índice NOAA PSL: [(año, mes, valor)]."""
    return ci.parse_psl(c._get(ci.PSL[key][1], timeout=25).text)


def phase(oni):
    if oni is None: return 'sin dato'
    if oni >= 2.0: return 'El Niño muy fuerte'
    if oni >= 1.5: return 'El Niño fuerte'
    if oni >= 1.0: return 'El Niño moderado'
    if oni >= 0.5: return 'El Niño débil'
    if oni <= -1.5: return 'La Niña fuerte'
    if oni <= -1.0: return 'La Niña moderada'
    if oni <= -0.5: return 'La Niña débil'
    return 'neutral'


def chain():
    jobs = {'cpac850': lambda: _cpc_index('cpac850'), 'wpac850': lambda: _cpc_index('wpac850'),
            'epac850': lambda: _cpc_index('epac850'), 'olr': lambda: _cpc_index('olr', ('ANOMALY', 'STANDARDIZED')),
            'heat': lambda: parse_heat(c._get(HEAT, timeout=25).text)}
    for k in ('nino34', 'nino12', 'oni', 'soi', 'meiv2'):
        jobs[k] = (lambda k=k: psl_series(k))
    res, errors = {}, {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {k: pool.submit(f) for k, f in jobs.items()}
        for k, f in futs.items():
            try:
                res[k] = f.result()
            except Exception as e:
                errors[k] = type(e).__name__

    def psl_rows(k):
        return res.get(k) or []

    steps = []
    # 1 · alisios
    w = {k: res[k][1] for k in ('wpac850', 'cpac850', 'epac850') if k in res}
    if w:
        cur = w.get('cpac850') or next(iter(w.values()))
        y, m, v = cur[-1]
        steps.append({'n': 1, 'key': 'alisios', 'title': 'Los alisios se debilitan',
                      'what': 'Viento del este a 1.500 m sobre el Pacífico ecuatorial (anomalía estandarizada). Negativo = alisios más débiles que lo normal.',
                      'value': round(v, 1), 'unit': 'desvíos', 'date': f'{MONTHS[m - 1]} {y}',
                      'signal': 'Niño' if v <= -1 else 'Niña' if v >= 1 else 'neutral',
                      'reading': ('Los alisios están muy debilitados: dejan de empujar el agua cálida hacia Indonesia.' if v <= -1.5 else
                                  'Los alisios están más débiles que lo normal.' if v <= -0.5 else
                                  'Los alisios están más fuertes que lo normal (típico de La Niña).' if v >= 0.5 else 'Alisios cerca de lo normal.'),
                      'series': {('Pacífico oeste' if k == 'wpac850' else 'Pacífico central' if k == 'cpac850' else 'Pacífico este'): _last(v2)
                                 for k, v2 in w.items()},
                      'records': records(cur), 'source': 'NOAA CPC · índices de viento 850 hPa'})
    # 2 · calor bajo el mar
    if res.get('heat'):
        y, m, v = res['heat'][-1]
        steps.append({'n': 2, 'key': 'calor', 'title': 'El agua cálida avanza hacia el este por debajo',
                      'what': 'Temperatura del océano entre 0 y 300 m en el Pacífico ecuatorial central-este, anomalía en °C. Anticipa lo que después aparece en superficie.',
                      'value': round(v, 2), 'unit': '°C', 'date': f'{MONTHS[m - 1]} {y}',
                      'signal': 'Niño' if v >= 0.5 else 'Niña' if v <= -0.5 else 'neutral',
                      'reading': (f'Hay {v:+.1f} °C de agua más caliente bajo la superficie: reserva de calor para sostener El Niño.' if v >= 1 else
                                  f'Agua subsuperficial {v:+.1f} °C respecto de lo normal.'),
                      'series': {'0-300 m (180°-100°O)': _last(res['heat'])}, 'records': records(res['heat']),
                      'source': 'NOAA CPC · contenido de calor del océano'})
    # 3 · superficie
    n34, oni, n12 = psl_rows('nino34'), psl_rows('oni'), psl_rows('nino12')
    if n34 or oni:
        last_oni = oni[-1] if oni else None
        last34 = n34[-1] if n34 else None
        steps.append({'n': 3, 'key': 'superficie', 'title': 'El mar se calienta en superficie',
                      'what': 'Temperatura del mar en Niño 3.4 (centro del Pacífico) y Niño 1+2 (costa de Perú y Ecuador). El ONI es el promedio de 3 meses que define la fase.',
                      'value': round(last34[2], 2) if last34 else None, 'unit': '°C (Niño 3.4)', 'date': f'{MONTHS[last34[1] - 1]} {last34[0]}' if last34 else '',
                      'oni': round(last_oni[2], 2) if last_oni else None, 'phase': phase(last_oni[2] if last_oni else None),
                      'nino12': round(n12[-1][2], 2) if n12 else None,
                      'signal': 'Niño' if (last_oni and last_oni[2] >= 0.5) else 'Niña' if (last_oni and last_oni[2] <= -0.5) else 'neutral',
                      'reading': f"Fase actual: {phase(last_oni[2]) if last_oni else 'sin dato'} (ONI {last_oni[2]:+.2f})." if last_oni else '',
                      'series': {'Niño 3.4': _last(n34), 'ONI': _last(oni), 'Niño 1+2': _last(n12)},
                      'records': records(n34), 'records_oni': records(oni), 'source': 'NOAA PSL'})
    # 4 · atmósfera
    soi, mei = psl_rows('soi'), psl_rows('meiv2')
    olr = res.get('olr', (None, []))[1]
    if soi or mei or olr:
        s = soi[-1] if soi else None
        steps.append({'n': 4, 'key': 'atmosfera', 'title': 'La atmósfera acompaña y lleva la lluvia',
                      'what': 'SOI: diferencia de presión Tahití-Darwin (negativo = El Niño). OLR: nubosidad sobre el Pacífico central (negativo = más nubes y tormentas). MEI combina mar y atmósfera.',
                      'value': round(s[2], 1) if s else None, 'unit': 'SOI', 'date': f'{MONTHS[s[1] - 1]} {s[0]}' if s else '',
                      'mei': round(mei[-1][2], 2) if mei else None, 'olr': round(olr[-1][2], 1) if olr else None,
                      'signal': 'Niño' if (s and s[2] <= -0.7) else 'Niña' if (s and s[2] >= 0.7) else 'neutral',
                      'reading': 'Mar y atmósfera están acoplados: El Niño está plenamente establecido.' if (s and s[2] <= -0.7 and mei and mei[-1][2] >= 1)
                                 else 'La atmósfera todavía no acompaña del todo al mar.' if (s and s[2] > -0.7) else '',
                      'series': {'SOI': _last(soi), 'MEI v2': _last(mei), 'OLR (anomalía)': _last(olr)},
                      'records': records(soi), 'records_mei': records(mei), 'source': 'NOAA PSL · NOAA CPC'})
    signals = [st['signal'] for st in steps]
    verdict = ('Cadena de El Niño completa: alisios débiles, calor bajo el mar, mar caliente y atmósfera acoplada.' if signals.count('Niño') >= 4 else
               'Señales de El Niño en varios eslabones.' if signals.count('Niño') >= 2 else
               'Cadena de La Niña.' if signals.count('Niña') >= 3 else 'Sin una fase definida en todos los eslabones.')
    ok = bool(steps)
    return c.envelope({'steps': steps, 'verdict': verdict, 'errors': errors,
                       'forecast_links': [{'name': 'IRI (Universidad de Columbia) · pronóstico de modelos', 'url': 'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/'},
                                          {'name': 'NOAA CPC · discusión mensual ENSO', 'url': 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml'},
                                          {'name': 'SMN Argentina · perspectiva trimestral', 'url': 'https://www.smn.gob.ar/pronostico-trimestral'}]},
                      'multi', 'cadena de El Niño, del Pacífico a la lluvia', 'NOAA CPC · NOAA PSL',
                      'recibido' if ok else 'sin dato', None if ok else 'No respondió ninguna fuente de la cadena')


# ───────────────────────── qué pasó en el lote en cada fase ─────────────────────────
def season_phase(oni_rows):
    """ONI promedio oct-dic de cada año → fase de la temporada oct(Y)-mar(Y+1)."""
    by = {}
    for y, m, v in oni_rows:
        if m in (10, 11, 12):
            by.setdefault(y, []).append(v)
    return {y: (round(mean(v), 2), phase(mean(v))) for y, v in by.items() if len(v) == 3}


def lot_impact(lat, lon):
    oni = psl_series('oni')
    end = c._now().date()
    env = c.external('https://archive-api.open-meteo.com/v1/archive',
                     {'latitude': lat, 'longitude': lon, 'start_date': '1991-01-01', 'end_date': f'{end.year}-{end.month:02d}-01',
                      'daily': 'precipitation_sum', 'models': 'era5', 'timezone': 'UTC'},
                     scope='lluvia de temporada por fase ENSO', organism='Copernicus ERA5 vía Open-Meteo')
    d = (env['data'] or {}).get('daily') or {}
    mon = {}
    for t, p in zip(d.get('time') or [], d.get('precipitation_sum') or []):
        if p is not None:
            k = (int(t[:4]), int(t[5:7])); mon[k] = mon.get(k, 0) + p
    return c.envelope(impact_from(mon, season_phase(oni)), 'multi', 'lluvia de octubre a marzo según fase ENSO', 'ERA5 · NOAA PSL')


def impact_from(mon, phases):
    seasons = []
    for y, (o, ph) in sorted(phases.items()):
        keys = [(y, m) for m in (10, 11, 12)] + [(y + 1, m) for m in (1, 2, 3)]
        if all(k in mon for k in keys):
            seasons.append({'season': f'{y}-{str(y + 1)[2:]}', 'oni': o, 'phase': ph, 'rain_mm': round(sum(mon[k] for k in keys))})
    neutral = [s['rain_mm'] for s in seasons if s['phase'] == 'neutral']
    base = median(neutral) if neutral else (median([s['rain_mm'] for s in seasons]) if seasons else None)
    for s in seasons:
        s['anomaly_pct'] = round((s['rain_mm'] / base - 1) * 100) if base else None
    groups = {}
    for label, test in (('El Niño', lambda p: p.startswith('El Niño')), ('El Niño fuerte o muy fuerte', lambda p: p in ('El Niño fuerte', 'El Niño muy fuerte')),
                        ('Neutral', lambda p: p == 'neutral'), ('La Niña', lambda p: p.startswith('La Niña'))):
        vals = [s['rain_mm'] for s in seasons if test(s['phase'])]
        if vals:
            groups[label] = {'n': len(vals), 'median_mm': round(median(vals)),
                             'vs_neutral_pct': round((median(vals) / base - 1) * 100) if base else None,
                             'wetter_than_neutral': sum(1 for v in vals if base and v > base)}
    strong = [s for s in seasons if s['phase'] in ('El Niño fuerte', 'El Niño muy fuerte')]
    g = groups.get('El Niño fuerte o muy fuerte') or groups.get('El Niño')
    reading = (f"En este punto, las temporadas de octubre a marzo con El Niño fuerte llovieron en la mediana {g['vs_neutral_pct']:+d} % respecto de los años neutrales "
               f"({g['wetter_than_neutral']} de {g['n']} temporadas por encima)." if g and g.get('vs_neutral_pct') is not None else
               'No hay suficientes temporadas para comparar.')
    wettest = sorted(seasons, key=lambda x: -x['rain_mm'])[:3]
    driest = sorted(seasons, key=lambda x: x['rain_mm'])[:3]
    return {'seasons': seasons, 'groups': groups, 'neutral_base_mm': round(base) if base else None,
            'wettest': wettest, 'driest': driest,
            'analog_seasons': [s['season'] for s in strong], 'reading': reading,
            'method': ('Lluvia acumulada de octubre a marzo (ERA5) en cada temporada desde 1991-92. La fase sale del ONI promedio de octubre a diciembre. '
                       'Es la historia del punto, no un pronóstico: cada El Niño es distinto.')}
