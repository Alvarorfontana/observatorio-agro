"""crop_water v1.0 — agua de cultivo con el método FAO-56 (base del paquete pyfao56).

Coeficiente de cultivo único (Kc) por etapa, agua total disponible (TAW), agua de riego fácilmente
disponible (RAW) y necesidad neta de riego. Es el método de la FAO (Allen y otros, 1998) que usa
pyfao56; acá se calcula para el lote con la ET₀ y la lluvia que DOTS ya trae de Open-Meteo y el agua
útil del suelo de SoilGrids (perfil_suelo). No reemplaza una medición de humedad en el lote.
"""
from datetime import date

CROPS = {
    'maiz':    {'name': 'Maíz',    'kc_ini': 0.30, 'kc_mid': 1.20, 'kc_end': 0.35, 'stages': (25, 35, 40, 30),  'zr': 1.0, 'p': 0.55},
    'soja':    {'name': 'Soja',    'kc_ini': 0.40, 'kc_mid': 1.15, 'kc_end': 0.50, 'stages': (20, 35, 60, 25),  'zr': 1.0, 'p': 0.50},
    'trigo':   {'name': 'Trigo',   'kc_ini': 0.40, 'kc_mid': 1.15, 'kc_end': 0.30, 'stages': (20, 30, 50, 30),  'zr': 1.2, 'p': 0.55},
    'girasol': {'name': 'Girasol', 'kc_ini': 0.35, 'kc_mid': 1.15, 'kc_end': 0.35, 'stages': (25, 35, 45, 25),  'zr': 1.0, 'p': 0.45},
    'sorgo':   {'name': 'Sorgo',   'kc_ini': 0.35, 'kc_mid': 1.10, 'kc_end': 0.35, 'stages': (20, 35, 45, 30),  'zr': 1.0, 'p': 0.55},
    'alfalfa': {'name': 'Alfalfa', 'kc_ini': 0.40, 'kc_mid': 1.15, 'kc_end': 0.90, 'stages': (10, 30, 200, 20), 'zr': 1.5, 'p': 0.55},
    'pastura': {'name': 'Pastura', 'kc_ini': 0.90, 'kc_mid': 1.00, 'kc_end': 0.90, 'stages': (0, 0, 365, 0),    'zr': 0.6, 'p': 0.55},
}
STAGE_NAMES = ['inicial', 'desarrollo', 'media', 'final', 'madurez']
IRRIGATION_EFFICIENCY = 0.75


def _frac(v):
    """θ en fracción o en % → fracción. SoilGrids llega como porcentaje (p. ej. 31,5)."""
    if v is None:
        return None
    return v / 100 if v > 1.5 else v


def _info(crop):
    return CROPS.get(crop) or CROPS['maiz']


def kc_for_day(crop, d):
    """Kc del día d (0 = siembra). Interpola inicial→media→final según las etapas del cultivo."""
    c = _info(crop)
    ini, dev, mid, late = c['stages']
    if d < ini:
        return c['kc_ini']
    if d < ini + dev:
        f = (d - ini) / dev if dev else 1.0
        return round(c['kc_ini'] + f * (c['kc_mid'] - c['kc_ini']), 3)
    if d < ini + dev + mid:
        return c['kc_mid']
    if d < ini + dev + mid + late:
        f = (d - ini - dev - mid) / late if late else 1.0
        return round(c['kc_mid'] - f * (c['kc_mid'] - c['kc_end']), 3)
    return c['kc_end']


def stage(crop, d):
    c = _info(crop)
    ini, dev, mid, late = c['stages']
    total = ini + dev + mid + late
    if d < 0:
        return {'key': 'previa', 'name': 'previa a la siembra', 'day': d, 'total_days': total}
    edges = [ini, ini + dev, ini + dev + mid, total]
    idx = next((i for i, e in enumerate(edges) if d < e), 4)
    return {'key': STAGE_NAMES[idx], 'name': STAGE_NAMES[idx], 'day': d, 'total_days': total}


def taw_mm(theta_fc, theta_wp, zr_m):
    """Agua total disponible (TAW) del perfil radicular, en mm = 1000 × (θfc − θwp) × Zr."""
    fc, wp = _frac(theta_fc), _frac(theta_wp)
    if fc is None or wp is None:
        return None
    return round(1000 * max(fc - wp, 0.0) * zr_m)


def advise(crop='maiz', sowing=None, et0=None, rain=None, theta_fc=None, theta_wp=None, today=None):
    """Programación de riego de la ventana pronosticada. Resultados en mm; 'sin dato' si falta un insumo."""
    c = _info(crop)
    et0 = et0 or []
    rain = rain or []
    today = date.fromisoformat(today) if isinstance(today, str) else (today or date.today())
    if isinstance(sowing, str):
        sowing = date.fromisoformat(sowing)
    d0 = (today - sowing).days if sowing else None
    n = len(et0)

    days, etc_sum, rain_sum = [], 0.0, 0.0
    for i in range(n):
        kc = _info(crop)['kc_mid'] if d0 is None else kc_for_day(crop, d0 + i)
        st = 'sin fecha' if d0 is None else stage(crop, d0 + i)['name']
        e = et0[i] or 0.0
        r = (rain[i] if i < len(rain) else 0.0) or 0.0
        etc = kc * e
        etc_sum += etc
        rain_sum += r
        days.append({'date': None, 'stage': st, 'kc': round(kc, 2), 'et0_mm': round(e, 1),
                     'etc_mm': round(etc, 1), 'rain_mm': round(r, 1), 'balance_mm': round(r - etc, 1)})
    if not days:
        raise ValueError('Sin pronóstico de ET₀ para programar el riego')

    taw = taw_mm(theta_fc, theta_wp, c['zr'])
    raw = None if taw is None else round(c['p'] * taw)
    net = max(0.0, etc_sum - rain_sum)
    out = {
        'crop': crop, 'crop_name': c['name'], 'sowing': sowing.isoformat() if sowing else None,
        'today': today.isoformat(), 'days_after_sowing': d0,
        'stage_today': 'sin fecha de siembra' if d0 is None else stage(crop, d0)['name'],
        'root_depth_m': c['zr'], 'taw_mm': taw, 'raw_mm': raw,
        'window_days': len(days), 'etc_total_mm': round(etc_sum, 1), 'rain_total_mm': round(rain_sum, 1),
        'net_irrigation_mm': round(net, 1),
        'gross_irrigation_mm': round(net / IRRIGATION_EFFICIENCY, 1) if net else 0.0,
        'days': days,
    }
    if taw:
        out['reading'] = (f"Para {c['name']} la ventana pide {round(etc_sum, 1)} mm de ETc y se esperan {round(rain_sum, 1)} mm de lluvia; "
                          f"necesidad neta de riego {round(net, 1)} mm (bruta {out['gross_irrigation_mm']} mm). "
                          f"Agua útil del perfil (0 a {c['zr']} m): {taw} mm, riego fácil hasta {raw} mm de déficit.")
    else:
        out['reading'] = (f"Para {c['name']} la ventana pide {round(etc_sum, 1)} mm de ETc y se esperan {round(rain_sum, 1)} mm de lluvia; "
                          f"necesidad neta de riego {round(net, 1)} mm. Sin dato de agua útil del suelo para acotar el riego.")
    return out
