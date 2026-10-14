"""salud v1.0 — clima y salud de la población en 80 localidades de Sudamérica: dengue y olas de calor.

Dengue (condiciones climáticas para el mosquito Aedes aegypti, no casos):
  - Aptitud térmica de la transmisión según la temperatura media diaria, con la curva de Mordecai et al. (2017,
    PLOS Neglected Tropical Diseases): nula por debajo de 17,8 °C y por encima de 34,6 °C, máxima cerca de 29 °C.
    Se usa la forma de Brière T·(T−T0)·√(Tm−T), normalizada a 1 en el máximo.
  - Agua para los criaderos: lluvia de los últimos 30 días (factor 0,4 sin lluvia, 1 con 100 mm o más; los
    recipientes con agua existen aunque no llueva).
  - Índice = aptitud térmica media de los últimos 14 días × factor de lluvia. Rangos: menos de 0,2 bajo ·
    0,2 a 0,45 moderado · 0,45 a 0,7 alto · más de 0,7 muy alto. Los casos confirmados están en el Boletín
    Epidemiológico Nacional del Ministerio de Salud.
Olas de calor (criterio del SMN): al menos 3 días seguidos con máxima y mínima iguales o mayores al percentil 90
del lugar. Mientras no esté calculado el percentil de cada localidad se usan umbrales fijos provisorios
(máxima 35 °C y mínima 22 °C), y se informa.
Datos: pronóstico y últimos 30 días de Open-Meteo (modelos globales y análisis), una sola consulta para todas las localidades.
"""
import json
import math
import os
import time

import research_connectors as c
import enso_sa

FORECAST = 'https://api.open-meteo.com/v1/forecast'
T0, TM = 17.8, 34.6
P90_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'calor_p90.json')
_CACHE = {}


def _briere(t):
    return 0.0 if t is None or t <= T0 or t >= TM else t * (t - T0) * math.sqrt(TM - t)


_MAX = max(_briere(T0 + i / 100) for i in range(int((TM - T0) * 100)))


def thermal(t):
    return round(_briere(t) / _MAX, 3)


def rain_factor(mm):
    return 0.4 if mm is None else round(min(1.0, 0.4 + 0.6 * mm / 100), 3)


def dengue_class(v):
    return 'sin dato' if v is None else 'bajo' if v < 0.2 else 'moderado' if v < 0.45 else 'alto' if v < 0.7 else 'muy alto'


def heatwave(days, tx90, tn90):
    """days: [(fecha, tmax, tmin)] → tramos de 3 o más días seguidos sobre ambos umbrales."""
    runs, cur = [], []
    for d, tx, tn in days:
        if tx is not None and tn is not None and tx >= tx90 and tn >= tn90:
            cur.append(d)
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = []
    if len(cur) >= 3:
        runs.append(cur)
    return [{'from': r[0], 'to': r[-1], 'days': len(r)} for r in runs]


def load_p90():
    import datastore
    return (datastore.load('calor_p90.json') or {}).get('places') or {}


def analyze_place(daily, today_iso, p90=None):
    t = daily.get('time') or []
    tmean, tmax, tmin, rain = (daily.get(k) or [None] * len(t) for k in ('temperature_2m_mean', 'temperature_2m_max', 'temperature_2m_min', 'precipitation_sum'))
    past = [i for i, d in enumerate(t) if d < today_iso]
    fut = [i for i, d in enumerate(t) if d >= today_iso]
    last14 = [thermal(tmean[i]) for i in past[-14:] if tmean[i] is not None]
    next16 = [thermal(tmean[i]) for i in fut if tmean[i] is not None]
    r30 = [rain[i] for i in past[-30:] if rain[i] is not None]
    rain30 = round(sum(r30)) if len(r30) >= 25 else None
    th = round(sum(last14) / len(last14), 3) if last14 else None
    idx = round(th * rain_factor(rain30), 3) if th is not None else None
    th_next = round(sum(next16) / len(next16), 3) if next16 else None
    idx_next = round(th_next * rain_factor(rain30), 3) if th_next is not None else None
    tx90, tn90, fixed = (p90['tx90'], p90['tn90'], False) if p90 else (35.0, 22.0, True)
    waves = heatwave([(t[i], tmax[i], tmin[i]) for i in fut], tx90, tn90)
    hot = [i for i in fut if tmax[i] is not None and tmax[i] >= tx90]
    return {'dengue_index': idx, 'dengue_class': dengue_class(idx), 'dengue_next_index': idx_next, 'dengue_next_class': dengue_class(idx_next),
            'thermal_14d': th, 'rain_30d_mm': rain30,
            'tmax_next': max((tmax[i] for i in fut if tmax[i] is not None), default=None),
            'heat_threshold': {'tx90': tx90, 'tn90': tn90, 'fixed': fixed},
            'heatwaves': waves, 'hot_days': len(hot),
            'heat_class': 'ola de calor' if waves else 'días muy calurosos' if hot else 'sin ola de calor'}


def live():
    hit = _CACHE.get('sa')
    if hit and time.monotonic() - hit[0] < 3 * 3600:
        return hit[1]
    pts = enso_sa.PLACES
    lat = ','.join(f'{p[3]:.2f}' for p in pts); lon = ','.join(f'{p[4]:.2f}' for p in pts)
    r = c.SESSION.get(FORECAST, params={'latitude': lat, 'longitude': lon, 'past_days': 31, 'forecast_days': 16, 'timezone': 'UTC',
                                         'daily': 'temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum'}, timeout=40)
    r.raise_for_status()
    js = r.json()
    js = js if isinstance(js, list) else [js]
    today = c._now().date().isoformat()
    p90 = load_p90()
    rows = []
    for i, p in enumerate(pts):
        d = (js[i] if i < len(js) else {}).get('daily') or {}
        rows.append({'id': p[0], 'name': p[1], 'country': p[2], 'lat': p[3], 'lon': p[4], **analyze_place(d, today, p90.get(p[0]))})
    counts = {}
    for row in rows:
        counts[row['dengue_class']] = counts.get(row['dengue_class'], 0) + 1
    out = {'places': rows, 'dengue_counts': counts, 'heatwave_places': [r['name'] for r in rows if r['heatwaves']],
           'p90_available': bool(p90), 'method': __doc__.split('\n\n', 1)[1].strip(),
           'official': [{'name': 'Boletín Epidemiológico Nacional (Ministerio de Salud)', 'url': 'https://www.argentina.gob.ar/salud/boletin-epidemiologico-nacional'},
                        {'name': 'Alertas por temperaturas extremas (SMN)', 'url': 'https://www.smn.gob.ar/alertas'}]}
    env = c.envelope(out, FORECAST, 'dengue y olas de calor en 80 localidades', 'Open-Meteo · DOTS')
    _CACHE['sa'] = (time.monotonic(), env)
    return env
