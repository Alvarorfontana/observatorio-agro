"""enso_sa v1.0 — El Niño en toda Sudamérica: qué se espera y qué está pasando ahora, localidad por localidad.

Dos partes:
  1. Referencia (se calcula una vez por mes en GitHub Actions con scripts/enso_sudamerica.py → data/enso_sudamerica.json):
     para cada localidad, lluvia diaria ERA5 desde 1991 → lluvia de cada temporada (octubre a marzo y mayo a septiembre)
     según la fase ENSO (ONI de NOAA) y la lluvia normal de cada mes (promedio 1991-2020).
  2. Ahora (en cada consulta, una sola llamada para todas las localidades): lluvia de los últimos 30 y 90 días (ERA5,
     ~6 días de demora) contra la normal de esos mismos días, y lluvia pronosticada para los próximos 16 días
     (modelos globales vía Open-Meteo) contra su normal.
Se compara lo que está pasando con lo que El Niño fuerte trajo históricamente en cada punto. Es diagnóstico, no pronóstico.
"""
import calendar
import json
import os
import time
from datetime import timedelta

import research_connectors as c

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
FORECAST = 'https://api.open-meteo.com/v1/forecast'
REF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'enso_sudamerica.json')

# id, nombre, país, lat, lon
PLACES = [
    ('corrientes', 'Corrientes', 'Argentina', -27.47, -58.83), ('resistencia', 'Resistencia', 'Argentina', -27.45, -58.99),
    ('posadas', 'Posadas', 'Argentina', -27.37, -55.90), ('formosa', 'Formosa', 'Argentina', -26.18, -58.17),
    ('reconquista', 'Reconquista', 'Argentina', -29.15, -59.65), ('santa-fe', 'Santa Fe', 'Argentina', -31.63, -60.70),
    ('parana', 'Paraná', 'Argentina', -31.73, -60.53), ('concordia', 'Concordia', 'Argentina', -31.39, -58.02),
    ('gualeguaychu', 'Gualeguaychú', 'Argentina', -33.01, -58.52), ('rosario', 'Rosario', 'Argentina', -32.95, -60.65),
    ('pergamino', 'Pergamino', 'Argentina', -33.89, -60.57), ('junin', 'Junín', 'Argentina', -34.59, -60.95),
    ('buenos-aires', 'Buenos Aires', 'Argentina', -34.60, -58.38), ('tandil', 'Tandil', 'Argentina', -37.32, -59.13),
    ('bahia-blanca', 'Bahía Blanca', 'Argentina', -38.72, -62.27), ('santa-rosa', 'Santa Rosa', 'Argentina', -36.62, -64.29),
    ('cordoba', 'Córdoba', 'Argentina', -31.42, -64.18), ('rio-cuarto', 'Río Cuarto', 'Argentina', -33.13, -64.35),
    ('santiago-del-estero', 'Santiago del Estero', 'Argentina', -27.78, -64.26), ('tucuman', 'Tucumán', 'Argentina', -26.82, -65.22),
    ('salta', 'Salta', 'Argentina', -24.79, -65.41), ('mendoza', 'Mendoza', 'Argentina', -32.89, -68.83),
    ('neuquen', 'Neuquén', 'Argentina', -38.95, -68.06), ('bariloche', 'Bariloche', 'Argentina', -41.13, -71.31),
    ('comodoro', 'Comodoro Rivadavia', 'Argentina', -45.86, -67.48),
    ('montevideo', 'Montevideo', 'Uruguay', -34.90, -56.16), ('salto-uy', 'Salto', 'Uruguay', -31.39, -57.96),
    ('tacuarembo', 'Tacuarembó', 'Uruguay', -31.71, -55.98),
    ('asuncion', 'Asunción', 'Paraguay', -25.26, -57.58), ('encarnacion', 'Encarnación', 'Paraguay', -27.33, -55.87),
    ('filadelfia', 'Filadelfia (Chaco)', 'Paraguay', -22.35, -60.03),
    ('porto-alegre', 'Porto Alegre', 'Brasil', -30.03, -51.23), ('santa-maria', 'Santa Maria', 'Brasil', -29.68, -53.81),
    ('passo-fundo', 'Passo Fundo', 'Brasil', -28.26, -52.41), ('chapeco', 'Chapecó', 'Brasil', -27.10, -52.62),
    ('florianopolis', 'Florianópolis', 'Brasil', -27.60, -48.55), ('foz-iguacu', 'Foz do Iguaçu', 'Brasil', -25.55, -54.59),
    ('curitiba', 'Curitiba', 'Brasil', -25.43, -49.27), ('londrina', 'Londrina', 'Brasil', -23.31, -51.16),
    ('sao-paulo', 'São Paulo', 'Brasil', -23.55, -46.63), ('campo-grande', 'Campo Grande', 'Brasil', -20.47, -54.62),
    ('rio-de-janeiro', 'Río de Janeiro', 'Brasil', -22.91, -43.17), ('belo-horizonte', 'Belo Horizonte', 'Brasil', -19.92, -43.94),
    ('goiania', 'Goiânia', 'Brasil', -16.68, -49.25), ('brasilia', 'Brasilia', 'Brasil', -15.79, -47.88),
    ('cuiaba', 'Cuiabá', 'Brasil', -15.60, -56.10), ('sinop', 'Sinop', 'Brasil', -11.86, -55.50),
    ('salvador', 'Salvador', 'Brasil', -12.97, -38.50), ('recife', 'Recife', 'Brasil', -8.05, -34.88),
    ('teresina', 'Teresina', 'Brasil', -5.09, -42.80), ('fortaleza', 'Fortaleza', 'Brasil', -3.73, -38.53),
    ('belem', 'Belém', 'Brasil', -1.46, -48.49), ('manaus', 'Manaos', 'Brasil', -3.12, -60.02),
    ('porto-velho', 'Porto Velho', 'Brasil', -8.76, -63.90),
    ('santa-cruz', 'Santa Cruz de la Sierra', 'Bolivia', -17.78, -63.18), ('trinidad-bo', 'Trinidad', 'Bolivia', -14.83, -64.90),
    ('la-paz', 'La Paz', 'Bolivia', -16.50, -68.15),
    ('la-serena', 'La Serena', 'Chile', -29.90, -71.25), ('valparaiso', 'Valparaíso', 'Chile', -33.05, -71.62),
    ('santiago', 'Santiago', 'Chile', -33.45, -70.67), ('talca', 'Talca', 'Chile', -35.43, -71.66),
    ('concepcion', 'Concepción', 'Chile', -36.83, -73.05), ('temuco', 'Temuco', 'Chile', -38.74, -72.60),
    ('puerto-montt', 'Puerto Montt', 'Chile', -41.47, -72.94),
    ('piura', 'Piura', 'Perú', -5.19, -80.63), ('chiclayo', 'Chiclayo', 'Perú', -6.77, -79.84),
    ('lima', 'Lima', 'Perú', -12.05, -77.04), ('cusco', 'Cusco', 'Perú', -13.53, -71.97), ('iquitos', 'Iquitos', 'Perú', -3.75, -73.25),
    ('guayaquil', 'Guayaquil', 'Ecuador', -2.19, -79.89), ('quito', 'Quito', 'Ecuador', -0.18, -78.47),
    ('bogota', 'Bogotá', 'Colombia', 4.71, -74.07), ('medellin', 'Medellín', 'Colombia', 6.24, -75.58),
    ('cali', 'Cali', 'Colombia', 3.45, -76.53), ('barranquilla', 'Barranquilla', 'Colombia', 10.96, -74.80),
    ('caracas', 'Caracas', 'Venezuela', 10.49, -66.88), ('maracaibo', 'Maracaibo', 'Venezuela', 10.65, -71.64),
    ('ciudad-bolivar', 'Ciudad Bolívar', 'Venezuela', 8.12, -63.55),
    ('georgetown', 'Georgetown', 'Guyana', 6.80, -58.16), ('paramaribo', 'Paramaribo', 'Surinam', 5.85, -55.20),
]
BY_ID = {p[0]: p for p in PLACES}


# ───────────────────────── referencia (GitHub Actions) ─────────────────────────
def monthly_totals(daily):
    mon = {}
    for t, p in zip(daily.get('time') or [], daily.get('precipitation_sum') or []):
        if p is None:
            continue
        k = (int(t[:4]), int(t[5:7]))
        a = mon.setdefault(k, [0.0, 0])
        a[0] += p; a[1] += 1
    # sólo meses completos
    return {k: v[0] for k, v in mon.items() if v[1] >= calendar.monthrange(*k)[1] - 1}


def normals_from(mon):
    out = []
    for m in range(1, 13):
        vals = [mon[(y, m)] for y in range(1991, 2021) if (y, m) in mon]
        out.append(round(sum(vals) / len(vals), 1) if len(vals) >= 20 else None)
    return out


def reference_for(mon, phases):
    import enso_chain as ec
    def slim(r):
        return {k: r[k] for k in ('groups', 'neutral_base_mm', 'seasons', 'wettest', 'driest', 'analog_seasons', 'reading')}
    return {'normals': normals_from(mon),
            'warm': slim(ec.impact_from(mon, phases, ec.WARM, 'octubre a marzo')),
            'cold': slim(ec.impact_from(mon, phases, ec.COLD, 'mayo a septiembre'))}


def load_ref():
    try:
        with open(REF_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ───────────────────────── ahora ─────────────────────────
def window_normal(normals, start, days):
    tot, d = 0.0, start
    for _ in range(days):
        n = normals[d.month - 1]
        if n is None:
            return None
        tot += n / calendar.monthrange(d.year, d.month)[1]
        d += timedelta(days=1)
    return tot


def pct(obs, normal):
    if obs is None or not normal or normal < 5:   # menos de 5 mm normales: el % no dice nada (zona seca o temporada seca)
        return None
    return round((obs / normal - 1) * 100)


def classify(expected, now):
    if expected is None:
        return 'sin referencia'
    if abs(expected) < 10:
        return 'El Niño no cambia mucho acá'
    if now is None:
        return 'sin dato'
    if abs(now) < 15:
        return 'todavía no se nota'
    return 'ya se nota' if (now > 0) == (expected > 0) else 'por ahora va al revés'


def _as_list(data):
    return data if isinstance(data, list) else [data]


def season_key(month):
    return 'warm' if month in (10, 11, 12, 1, 2, 3) else 'cold'


def _phase_now():
    try:
        import enso_chain as ec
        rows = ec.psl_series('oni')
        y, m, v = rows[-1]
        return {'oni': round(v, 2), 'phase': ec.phase(v), 'period': f"{ec.MONTHS[m - 1]} {y}"}
    except Exception:
        return None


_LIVE = {}


def point_now(lat, lon, normals):
    """Lluvia de los últimos 30/90 días y próximos 16 en un punto (el lote) contra su normal."""
    today = c._now().date()
    end = today - timedelta(days=6)
    start = end - timedelta(days=89)
    d = c._get(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': start.isoformat(), 'end_date': end.isoformat(),
                         'daily': 'precipitation_sum', 'models': 'era5', 'timezone': 'UTC'}, timeout=30).json().get('daily') or {}
    vals = d.get('precipitation_sum') or []
    ok = [v for v in vals if v is not None]
    obs90 = round(sum(ok)) if len(ok) >= 80 else None
    last = [v for v in vals[-30:] if v is not None]
    obs30 = round(sum(last)) if len(last) >= 27 else None
    try:
        fd = c._get(FORECAST, {'latitude': lat, 'longitude': lon, 'daily': 'precipitation_sum', 'forecast_days': 16, 'timezone': 'UTC'},
                    timeout=20).json().get('daily') or {}
        fv = [v for v in (fd.get('precipitation_sum') or []) if v is not None]
        next16 = round(sum(fv)) if len(fv) >= 14 else None
    except Exception:
        next16 = None
    n90 = window_normal(normals, start, 90) if normals else None
    n30 = window_normal(normals, end - timedelta(days=29), 30) if normals else None
    n16 = window_normal(normals, today, 16) if normals else None
    return {'obs90_mm': obs90, 'normal90_mm': None if n90 is None else round(n90), 'now90_pct': pct(obs90, n90),
            'obs30_mm': obs30, 'normal30_mm': None if n30 is None else round(n30), 'now30_pct': pct(obs30, n30),
            'next16_mm': next16, 'normal16_mm': None if n16 is None else round(n16), 'next16_pct': pct(next16, n16),
            'window': {'from': start.isoformat(), 'to': end.isoformat()}}


def live():
    key = 'sa'
    hit = _LIVE.get(key)
    if hit and time.monotonic() - hit[0] < 3 * 3600:
        return hit[1]
    ref = load_ref() or {}
    rplaces = ref.get('places') or {}
    pts = [(p[0], p[1], p[2], p[3], p[4]) for p in PLACES]
    lat = ','.join(f'{p[3]:.2f}' for p in pts); lon = ','.join(f'{p[4]:.2f}' for p in pts)
    today = c._now().date()
    end = today - timedelta(days=6)
    start = end - timedelta(days=89)
    live_error = None
    try:
        past = c._get(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': start.isoformat(), 'end_date': end.isoformat(),
                                'daily': 'precipitation_sum', 'models': 'era5', 'timezone': 'UTC'}, timeout=40).json()
    except Exception as e:   # sin lluvia reciente igual se muestra lo que trae El Niño en cada lugar
        past, live_error = [], f'La lluvia reciente no respondió ({type(e).__name__}); se muestra sólo la referencia histórica.'
        if not rplaces:
            raise
    try:
        fut = _as_list(c._get(FORECAST, {'latitude': lat, 'longitude': lon, 'daily': 'precipitation_sum', 'forecast_days': 16,
                                         'timezone': 'UTC'}, timeout=30).json())
    except Exception:
        fut = []
    past = _as_list(past)
    skey = season_key(today.month)
    rows = []
    for i, p in enumerate(pts):
        d = (past[i] if i < len(past) else {}).get('daily') or {}
        vals = [v for v in (d.get('precipitation_sum') or [])]
        ok = [v for v in vals if v is not None]
        obs90 = round(sum(ok)) if len(ok) >= 80 else None
        obs30 = round(sum(v for v in vals[-30:] if v is not None)) if len([v for v in vals[-30:] if v is not None]) >= 27 else None
        fd = (fut[i] if i < len(fut) else {}).get('daily') or {}
        fv = [v for v in (fd.get('precipitation_sum') or []) if v is not None]
        next16 = round(sum(fv)) if len(fv) >= 14 else None
        r = rplaces.get(p[0]) or {}
        normals = r.get('normals')
        n90 = window_normal(normals, start, 90) if normals else None
        n30 = window_normal(normals, end - timedelta(days=29), 30) if normals else None
        n16 = window_normal(normals, today, 16) if normals else None
        g = ((r.get(skey) or {}).get('groups') or {})
        strong = g.get('El Niño fuerte o muy fuerte') or g.get('El Niño') or {}
        expected = strong.get('vs_neutral_pct')
        now90 = pct(obs90, n90)
        rows.append({'id': p[0], 'name': p[1], 'country': p[2], 'lat': p[3], 'lon': p[4],
                     'obs90_mm': obs90, 'normal90_mm': None if n90 is None else round(n90), 'now90_pct': now90,
                     'obs30_mm': obs30, 'normal30_mm': None if n30 is None else round(n30), 'now30_pct': pct(obs30, n30),
                     'next16_mm': next16, 'normal16_mm': None if n16 is None else round(n16), 'next16_pct': pct(next16, n16),
                     'expected_pct': expected, 'expected_n': strong.get('n'),
                     'expected_wetter': strong.get('wetter_than_neutral'),
                     'signal': classify(expected, now90)})
    counts = {}
    for r in rows:
        counts[r['signal']] = counts.get(r['signal'], 0) + 1
    out = {'places': rows, 'counts': counts, 'phase_now': _phase_now(),
           'season': 'octubre a marzo' if skey == 'warm' else 'mayo a septiembre',
           'window': {'from': start.isoformat(), 'to': end.isoformat(), 'forecast_from': today.isoformat()},
           'reference': {'available': bool(rplaces), 'built': ref.get('built'), 'period': ref.get('period'), 'places': len(rplaces)},
           'live_error': live_error,
           'method': __doc__.split('\n\n', 1)[1].strip()}
    env = c.envelope(out, 'multi', 'El Niño en Sudamérica: esperado y observado', 'Copernicus ERA5 vía Open-Meteo · NOAA PSL')
    if not live_error:
        _LIVE[key] = (time.monotonic(), env)
    return env


def place_detail(pid):
    ref = load_ref() or {}
    r = (ref.get('places') or {}).get(pid)
    p = BY_ID.get(pid)
    if not r or not p:
        raise LookupError('Sin referencia para esa localidad')
    import enso_chain as ec
    out = dict(r['warm'])
    out['cold'] = r['cold']
    out['place'] = {'id': p[0], 'name': p[1], 'country': p[2], 'lat': p[3], 'lon': p[4]}
    out['method'] = ('Lluvia acumulada de octubre a marzo (ERA5) en cada temporada desde 1991. La fase sale del ONI promedio de octubre a diciembre. '
                     'Es la historia del punto, no un pronóstico: cada El Niño es distinto.')
    return c.envelope(out, 'multi', f'El Niño en {p[1]}', 'ERA5 · NOAA PSL')
