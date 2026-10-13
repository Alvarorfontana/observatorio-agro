"""water_balance v1.0 — balance de agua climático y sequía (índice tipo SPEI) desde 1991.

Datos: ERA5 (Copernicus) vía Open-Meteo Archive, diario: precipitación y evapotranspiración de referencia
FAO-56 Penman-Monteith (ET0). Balance mensual = lluvia − ET0 (lo que el ambiente "pide" vs lo que llueve).
Índice de sequía: balance acumulado de 1, 3, 6 y 12 meses estandarizado contra el mismo período de 1991-2020
(percentil empírico llevado a una normal estándar, como el SPEI). Mismo concepto que el déficit de TerraClimate.
"""
from datetime import date, timedelta
from statistics import NormalDist, median

import research_connectors as c

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def classify(z):
    if z is None: return 'sin dato'
    if z <= -2: return 'sequía extrema'
    if z <= -1.5: return 'sequía severa'
    if z <= -1: return 'sequía moderada'
    if z < 1: return 'normal'
    if z < 1.5: return 'húmedo'
    if z < 2: return 'muy húmedo'
    return 'extremadamente húmedo'


def monthly(daily):
    """daily: dict con time, precipitation_sum, et0_fao_evapotranspiration → {(y,m): [P, ET0, días]}"""
    out = {}
    for t, p, e in zip(daily.get('time') or [], daily.get('precipitation_sum') or [], daily.get('et0_fao_evapotranspiration') or []):
        if p is None or e is None:
            continue
        k = (int(t[:4]), int(t[5:7]))
        a = out.setdefault(k, [0.0, 0.0, 0])
        a[0] += p; a[1] += e; a[2] += 1
    return out


def standardize(value, ref):
    ref = [r for r in ref if r is not None]
    if value is None or len(ref) < 15:
        return None
    below = sum(1 for r in ref if r < value) + 0.5 * sum(1 for r in ref if r == value)
    p = min(max((below + 0.5) / (len(ref) + 1), 0.01), 0.99)
    return round(NormalDist().inv_cdf(p), 2)


def analyze_series(daily, today=None):
    today = today or c._now().date()
    mon = monthly(daily)
    # sólo meses completos (≥ 27 días con dato)
    full = {k: v for k, v in mon.items() if v[2] >= 27}
    keys = sorted(full)
    if len(keys) < 36:
        raise ValueError('Serie demasiado corta para calcular el índice de sequía')
    bal = {k: full[k][0] - full[k][1] for k in keys}
    last = keys[-1]

    def acc(end, n):
        y, m = end; s = 0.0
        for i in range(n):
            mm = m - i; yy = y
            while mm <= 0: mm += 12; yy -= 1
            if (yy, mm) not in bal: return None
            s += bal[(yy, mm)]
        return s

    spei = {}
    for n in (1, 3, 6, 12):
        cur = acc(last, n)
        ref = [acc((y, last[1]), n) for y in range(1991, 2021)]
        z = standardize(cur, ref)
        spei[str(n)] = {'balance_mm': None if cur is None else round(cur), 'normal_mm': round(median([r for r in ref if r is not None])) if any(r is not None for r in ref) else None,
                        'index': z, 'class': classify(z)}
    recent = []
    for k in keys[-12:]:
        p, e, _ = full[k]
        ref = [bal[(y, k[1])] for y in range(1991, 2021) if (y, k[1]) in bal]
        recent.append({'period': f'{MONTHS[k[1] - 1]} {k[0]}', 'rain_mm': round(p), 'et0_mm': round(e), 'balance_mm': round(p - e),
                       'normal_balance_mm': round(median(ref)) if ref else None})
    annual = []
    for y in sorted({k[0] for k in keys}):
        ms = [k for k in keys if k[0] == y]
        if len(ms) == 12:
            annual.append({'year': y, 'rain_mm': round(sum(full[k][0] for k in ms)), 'et0_mm': round(sum(full[k][1] for k in ms)),
                           'balance_mm': round(sum(bal[k] for k in ms))})
    deficit_months = sum(1 for r in recent if r['balance_mm'] < 0)
    return {'last_month': f'{MONTHS[last[1] - 1]} {last[0]}', 'spei': spei, 'recent': recent, 'annual': annual[-35:],
            'deficit_months_last12': deficit_months,
            'reading': (f"Últimos 3 meses: {spei['3']['class']} (índice {spei['3']['index']}). "
                        f"En el último año hubo {deficit_months} meses con más evapotranspiración que lluvia.")}


def water_balance(lat, lon):
    end = c._now().date() - timedelta(days=6)        # ERA5 se publica con ~5 días de demora
    env = c.external(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': '1991-01-01', 'end_date': end.isoformat(),
                               'daily': 'precipitation_sum,et0_fao_evapotranspiration', 'models': 'era5', 'timezone': 'UTC'},
                     scope='balance de agua y sequía (ERA5)', organism='Copernicus ERA5 vía Open-Meteo')
    data = analyze_series((env['data'] or {}).get('daily') or {})
    data.update(capability='ANALYSIS', method=__doc__.split('\n\n', 1)[1].strip())
    return c.envelope(data, ARCHIVE, 'balance de agua y sequía desde 1991', 'Copernicus ERA5 vía Open-Meteo')
