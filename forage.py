"""forage v3.1 — producción de pasto (PPNA aérea) y carga recomendada por lote.

Modelo de Monteith, como en el seguimiento forrajero satelital de la región pampeana:
  PPNA (kg MS/ha/día) = fPAR × RFA × EUR × 10
    fPAR = 1,25 × NDVI − 0,025   (acotado a 0–0,95)
    RFA  = 0,48 × radiación global diaria (MJ/m²/día)  — Open-Meteo / ERA5
    EUR  = eficiencia en el uso de la radiación (g MS/MJ RFA absorbida), según tipo de recurso
El NDVI diario se interpola entre las escenas Sentinel-2 válidas del lote.
Carga: EV/ha = PPNA × factor de uso / consumo diario de un EV (10 kg MS/día).
Los coeficientes son orientativos y se informan; conviene calibrarlos con cortes a campo.
"""
from datetime import date, timedelta

import research_connectors as c

RUE = {  # g MS / MJ RFA absorbida (valores orientativos de bibliografía regional)
    'pastizal': ('Pastizal natural', 0.4),
    'templada': ('Pastura implantada templada', 0.8),
    'megatermica': ('Pastura megatérmica (C4)', 1.0),
    'verdeo': ('Verdeo de invierno', 0.9),
}
EV_KG_DAY = 10.0      # consumo de un equivalente vaca (EV) en kg MS/día
DEFAULT_USE = 0.5     # fracción del pasto producido que se cosecha sin degradar el recurso


def fpar(ndvi):
    return min(0.95, max(0.0, 1.25 * ndvi - 0.025))


def interpolate(series, days):
    """series: [(date, ndvi)] ordenada. Devuelve NDVI por día (interpolación lineal, extremos constantes)."""
    pts = sorted(series)
    out = {}
    for d in days:
        prev = [p for p in pts if p[0] <= d]; nxt = [p for p in pts if p[0] >= d]
        if prev and nxt:
            (d0, v0), (d1, v1) = prev[-1], nxt[0]
            out[d] = v0 if d0 == d1 else v0 + (v1 - v0) * (d - d0).days / (d1 - d0).days
        elif prev:
            out[d] = prev[-1][1]
        elif nxt:
            out[d] = nxt[0][1]
    return out


def radiation(lat, lon, days=92):
    env = c.external('https://api.open-meteo.com/v1/forecast', {
        'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'past_days': days, 'forecast_days': 1,
        'daily': 'shortwave_radiation_sum'}, scope='radiación global diaria', organism='Open-Meteo')
    d = env['data'].get('daily') or {}
    return {date.fromisoformat(t): v for t, v in zip(d.get('time') or [], d.get('shortwave_radiation_sum') or []) if v is not None}


def estimate(ndvi_series, rad, area_ha, kind='pastizal', use=DEFAULT_USE, heads=None):
    if kind not in RUE:
        raise ValueError('Tipo de recurso desconocido')
    use = float(use)
    if not 0.2 <= use <= 0.8:
        raise ValueError('Factor de uso fuera de rango (0,2–0,8)')
    pts = []
    for r in ndvi_series or []:
        if r.get('status') == 'válida' and r.get('ndvi_mean') is not None:
            try:
                pts.append((date.fromisoformat(str(r.get('datetime') or r.get('from'))[:10]), float(r['ndvi_mean'])))
            except ValueError:
                pass
    if len(pts) < 2:
        raise ValueError('Hacen falta al menos dos escenas NDVI válidas del lote')
    if not rad:
        raise ValueError('Sin radiación solar para el período')
    start, end = min(p[0] for p in pts), max(rad)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    nd = interpolate(pts, days)
    label, eur = RUE[kind]
    daily = []
    for d in days:
        if d not in rad or d not in nd:
            continue
        par = 0.48 * rad[d]
        g = fpar(nd[d]) * par * eur * 10          # kg MS/ha/día
        daily.append({'date': d.isoformat(), 'ndvi': round(nd[d], 3), 'rad': round(rad[d], 1), 'ppna': round(g, 1)})
    if not daily:
        raise ValueError('No coinciden fechas de NDVI y radiación')
    last30 = daily[-30:]
    rate = sum(x['ppna'] for x in last30) / len(last30)
    total = sum(x['ppna'] for x in daily)
    ev_ha = rate * use / EV_KG_DAY
    months = {}
    for x in daily:
        k = x['date'][:7]
        months.setdefault(k, []).append(x['ppna'])
    out = {
        'capability': 'ANALYSIS', 'kind': kind, 'kind_label': label, 'rue': eur, 'use': use,
        'period': [daily[0]['date'], daily[-1]['date']], 'area_ha': area_ha,
        'growth_rate_30d': round(rate, 1), 'accumulated': round(total, 0), 'accumulated_days': len(daily),
        'monthly': [{'month': k, 'rate': round(sum(v) / len(v), 1), 'total': round(sum(v), 0)} for k, v in sorted(months.items())],
        'daily': daily[-60:],
        'ev_ha': round(ev_ha, 2), 'ev_lot': round(ev_ha * area_ha, 0) if area_ha else None,
        'assumptions': {'fpar': 'fPAR = 1,25·NDVI − 0,025', 'par': 'RFA = 0,48 × radiación global',
                        'rue': f'EUR {eur} g MS/MJ ({label})', 'ev': f'1 EV = {EV_KG_DAY:.0f} kg MS/día', 'use': f'uso {use:.0%}'},
        'note': 'Estimación orientativa de crecimiento aéreo. Calibrar la eficiencia con cortes de pasto a campo antes de ajustar carga.',
    }
    if heads and area_ha:
        out['current_load_ev_ha'] = round(heads / area_ha, 2)
        out['load_balance'] = ('carga por encima de lo que crece el pasto' if heads / area_ha > ev_ha * 1.1 else
                               'carga dentro de lo que crece el pasto' if heads / area_ha >= ev_ha * 0.6 else
                               'carga por debajo de lo que permite el crecimiento')
    return out


def forage(lat, lon, polygon=None, ndvi=None, kind='pastizal', use=DEFAULT_USE, heads=None):
    import vegetation as veg
    pts = veg.require_polygon(polygon)
    area = veg.area_ha(pts)
    if not ndvi or not ndvi.get('series'):
        ndvi = veg.ndvi_open(pts, days=120, scenes=8)['data']
    rad = radiation(lat, lon)
    data = estimate(ndvi.get('series'), rad, area, kind, use, heads)
    return c.envelope(data, 'https://api.open-meteo.com/v1/forecast', 'producción de pasto y carga',
                      'DOTS · Sentinel-2 + Open-Meteo (modelo de Monteith)')
