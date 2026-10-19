"""crop_suitability v1.0 — aptitud de cultivos de referencia para un punto.

Adopta el enfoque de OpenFarm (`openfarm.earth`, BSD-3): cada cultivo trae un **perfil de envolventes**
(temperatura, lluvia, pH y textura/drenaje) que se puntúa contra el clima normal y el suelo del lugar.
El puntaje global es el **mínimo** de los factores: manda el factor limitante, no el promedio (el mismo
criterio que `spray_window.py`). Los perfiles son datos planos inspirados en las fichas de FAO EcoCrop.

No inventa: sin clima o sin suelo queda en 'sin dato'. Es una aptitud de referencia climática-edáfica:
no mira manejo, riego, plagas ni mercado.
"""
import math

import research_connectors as c
import scales

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
CLIM_YEARS = 10
SOURCE = 'https://github.com/superzero11/OpenFarm'
ORGANISM = 'OpenFarm (BSD-3) · FAO EcoCrop · Open-Meteo ERA5 · ISRIC SoilGrids'
SCALE = 'crop_suitability'
METHODO = ('Aptitud por envolventes (temperatura, lluvia, pH y textura), inspirada en OpenFarm (BSD-3) y las '
           'fichas de FAO EcoCrop. Cada factor va de 0 a 100 (100 dentro del óptimo) y el puntaje global es el '
           'mínimo: manda el factor limitante. El clima es la normal ERA5 de los últimos 10 años; el suelo, SoilGrids 0-5 cm.')
CAVEAT = ('Aptitud climática-edáfica de referencia: no considera manejo, riego, plagas, salinidad ni mercado. '
          'Un puntaje bajo marca el factor que limita, no una imposibilidad.')

# (opt_lo, opt_hi, abs_lo, abs_hi) por factor. t: °C media anual; p: mm/año; ph: unidades; tex: fracción de arcilla.
CROPS = {
    'maiz':    {'name': 'Maíz',    't': (18, 32, 10, 47), 'p': (600, 1200, 400, 2000), 'ph': (5.8, 7.2, 4.5, 8.3), 'tex': (0.15, 0.35, 0.00, 0.55)},
    'soja':    {'name': 'Soja',    't': (20, 30, 10, 45), 'p': (600, 1000, 400, 1500), 'ph': (6.0, 7.0, 4.5, 8.4), 'tex': (0.20, 0.40, 0.05, 0.55)},
    'trigo':   {'name': 'Trigo',   't': (15, 25, 3, 38),  'p': (400, 800, 250, 1500),  'ph': (6.0, 7.5, 4.5, 8.5), 'tex': (0.15, 0.35, 0.00, 0.55)},
    'girasol': {'name': 'Girasol', 't': (18, 30, 8, 42),  'p': (500, 1000, 400, 1500), 'ph': (6.0, 7.5, 4.5, 8.5), 'tex': (0.15, 0.35, 0.05, 0.50)},
    'sorgo':   {'name': 'Sorgo',   't': (22, 35, 12, 45), 'p': (400, 800, 300, 1200),  'ph': (5.5, 8.0, 4.5, 8.5), 'tex': (0.15, 0.45, 0.00, 0.60)},
    'alfalfa': {'name': 'Alfalfa', 't': (15, 25, 4, 38),  'p': (500, 900, 300, 1600),  'ph': (6.0, 7.5, 5.0, 8.5), 'tex': (0.10, 0.30, 0.00, 0.50)},
    'pastura': {'name': 'Pastura', 't': (15, 25, 4, 38),  'p': (500, 1200, 300, 1500), 'ph': (5.5, 7.5, 4.5, 8.5), 'tex': (0.15, 0.40, 0.00, 0.60)},
}
FACTORS = {'t': 'Temperatura', 'p': 'Lluvia', 'ph': 'pH del suelo', 'tex': 'Textura (drenaje)'}
LABELS = [(80.0, 'muy apto', 'ok'), (60.0, 'apto', 'ok'), (40.0, 'marginal', 'warn'), (0.0, 'no apto', 'risk')]


def _now():
    return c._now()


def crop_of(name):
    key = str(name or 'maiz').strip().lower()
    return key if key in CROPS else 'maiz'


def score(x, env):
    """Puntaje 0-100 de un valor dentro de una envolvente (opt_lo, opt_hi, abs_lo, abs_hi)."""
    if x is None or env is None:
        return None
    opt_lo, opt_hi, abs_lo, abs_hi = env
    if opt_lo <= x <= opt_hi:
        return 100.0
    if x < opt_lo:
        return max(0.0, min(100.0, 100.0 * (x - abs_lo) / (opt_lo - abs_lo))) if opt_lo > abs_lo else 0.0
    return max(0.0, min(100.0, 100.0 * (abs_hi - x) / (abs_hi - opt_hi))) if abs_hi > opt_hi else 0.0


def _label(s):
    return next((lab, tone) for cut, lab, tone in LABELS if s >= cut)


def _climate(lat, lon):
    """Normal ERA5 de los últimos CLIM_YEARS años: temperatura media (°C) y lluvia anual (mm)."""
    y = _now().year
    js = c.external(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': f'{y - CLIM_YEARS}-01-01',
                              'end_date': f'{y - 1}-12-31', 'daily': 'temperature_2m_mean,precipitation_sum',
                              'timezone': 'UTC', 'models': 'era5'}).get('data') or {}
    daily = js.get('daily') or {}
    temps = [v for v in daily.get('temperature_2m_mean') or [] if v is not None]
    prec = [v for v in daily.get('precipitation_sum') or [] if v is not None]
    if not temps or not prec:
        return None
    return {'t_mean': round(sum(temps) / len(temps), 1), 'p_annual': round(sum(prec) / CLIM_YEARS), 'years': CLIM_YEARS}


def _soil(lat, lon):
    """pH del suelo (0-5 cm) y fracción de arcilla (arcilla / (arcilla + arena)) desde SoilGrids."""
    env = c.soil_full(lat, lon)
    rows = ((env.get('data') or {}).get('dots_summary') or {}).get('rows')
    if not rows:
        return None
    by = {r['key']: (r.get('by_depth') or {}) for r in rows}
    ph = (by.get('phh2o') or {}).get('0-5cm')
    clay = (by.get('clay') or {}).get('0-5cm')
    sand = (by.get('sand') or {}).get('0-5cm')
    tex = clay / (clay + sand) if (clay is not None and sand is not None and (clay + sand) > 0) else None
    if ph is None and tex is None:
        return None
    return {'ph': ph, 'clay_frac': round(tex, 3) if tex is not None else None}


def _reading(d):
    lim = d.get('limiting')
    base = (f"{d['crop_name']}: aptitud {d['overall']}/100 ({d['scale']['label']}). "
            f"Temperatura {d['factors']['t']['score']}, lluvia {d['factors']['p']['score']}, "
            f"pH {d['factors']['ph']['score']}, textura {d['factors']['tex']['score']}.")
    return base + (f" Limita {FACTORS[lim].lower()}." if lim else '')


def analyze(lat, lon, crop='maiz'):
    key = crop_of(crop)
    cw = CROPS[key]
    clim = _climate(lat, lon)
    if clim is None:
        return c.envelope(None, SOURCE, 'aptitud de cultivos (envolventes)', ORGANISM, 'sin dato',
                          'No se pudo leer el clima normal (Open-Meteo ERA5) del punto.')
    soil = _soil(lat, lon)
    if soil is None:
        return c.envelope(None, SOURCE, 'aptitud de cultivos (envolventes)', ORGANISM, 'sin dato',
                          'SoilGrids no tiene suelo en el punto ni en sus vecinos.')

    values = {'t': clim['t_mean'], 'p': clim['p_annual'], 'ph': soil['ph'], 'tex': soil['clay_frac']}
    factors = {}
    for f, env in cw.items():
        if f == 'name':
            continue
        s = score(values.get(f), env)
        if s is None:
            continue
        lab, tone = _label(s)
        factors[f] = {'label': FACTORS[f], 'value': values[f], 'score': round(s, 1), 'class': lab, 'tone': tone}

    if not factors:
        return c.envelope(None, SOURCE, 'aptitud de cultivos (envolventes)', ORGANISM, 'sin dato',
                          'No hubo factores con dato para puntuar.')
    limiting = min(factors, key=lambda f: factors[f]['score'])
    overall = factors[limiting]['score']
    data = {'crop': key, 'crop_name': cw['name'], 'overall': overall, 'limiting': limiting,
            'factors': factors, 'climate': {'t_mean_c': clim['t_mean'], 'p_annual_mm': clim['p_annual'], 'years': clim['years']},
            'soil': soil, 'scale': scales.band(SCALE, overall), 'method': METHODO, 'caveat': CAVEAT}
    data['reading'] = _reading(data)
    return c.envelope(data, SOURCE, 'aptitud de cultivos (envolventes)', ORGANISM)
