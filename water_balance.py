"""water_balance v1.0 — balance de agua climático y sequía (índice tipo SPEI) desde 1991.

Datos: ERA5 (Copernicus) vía Open-Meteo Archive, diario: precipitación y evapotranspiración de referencia
FAO-56 Penman-Monteith (ET0). Balance mensual = lluvia − ET0 (lo que el ambiente "pide" vs lo que llueve).
Índice de sequía SPEI (Vicente-Serrano y otros, 2010): balance acumulado de 1, 3, 6 y 12 meses ajustado a una
distribución log-logística de tres parámetros con los momentos ponderados por probabilidad de 1991-2020 (el mismo
método del paquete SPEI de R), llevado a una normal estándar. Si el ajuste no es válido se usa el percentil empírico.
El cálculo se contrasta en cada revisión automática con la librería climate_indices (scripts/validar_indices.py).
"""
import math
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


def loglogistic_fit(ref):
    """Parámetros (alfa, beta, gamma) por momentos ponderados por probabilidad insesgados (Hosking; paquete SPEI)."""
    x = sorted(r for r in ref if r is not None)
    n = len(x)
    if n < 15:
        return None
    w0 = sum(x) / n
    w1 = sum(x[i] * (n - 1 - i) / (n - 1) for i in range(n)) / n
    w2 = sum(x[i] * (n - 1 - i) * (n - 2 - i) / ((n - 1) * (n - 2)) for i in range(n)) / n
    den = 6 * w1 - w0 - 6 * w2
    if den == 0:
        return None
    beta = (2 * w1 - w0) / den
    if not beta > 1:
        return None
    g = math.gamma(1 + 1 / beta) * math.gamma(1 - 1 / beta)
    alpha = (w0 - 2 * w1) * beta / g
    if not alpha > 0:
        return None
    return alpha, beta, w0 - alpha * g


def spei_value(value, ref):
    """SPEI con distribución log-logística; None si el ajuste no es válido."""
    fit = loglogistic_fit(ref) if value is not None else None
    if not fit:
        return None
    a, b, g = fit
    f = 1e-6 if value <= g else 1 / (1 + (a / (value - g)) ** b)
    f = min(max(f, 1e-6), 1 - 1e-6)
    return round(max(-3.09, min(3.09, NormalDist().inv_cdf(f))), 2)


def standardize(value, ref):
    z = spei_value(value, ref)
    if z is not None:
        return z
    return empirical(value, ref)


def empirical(value, ref):
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
    from concurrent.futures import ThreadPoolExecutor
    import perfil_suelo
    pool = ThreadPoolExecutor(max_workers=1)
    prof = pool.submit(perfil_suelo.soil_profile, lat, lon)   # en paralelo con el balance
    end = c._now().date() - timedelta(days=6)        # ERA5 se publica con ~5 días de demora
    env = c.external(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': '1991-01-01', 'end_date': end.isoformat(),
                               'daily': 'precipitation_sum,et0_fao_evapotranspiration', 'models': 'era5', 'timezone': 'UTC'},
                     scope='balance de agua y sequía (ERA5)', organism='Copernicus ERA5 vía Open-Meteo')
    daily = (env.get('data') or {}).get('daily') or {}
    if not daily.get('time') or not daily.get('precipitation_sum') or not daily.get('et0_fao_evapotranspiration'):
        pool.shutdown(wait=False)
        return c.envelope(None, ARCHIVE, 'balance de agua y sequía desde 1991', 'Copernicus ERA5 vía Open-Meteo', 'sin dato', env.get('error') or 'ERA5 no entregó una serie diaria completa de lluvia y evapotranspiración')
    data = analyze_series(daily)
    data.update(capability='ANALYSIS', method=__doc__.split('\n\n', 1)[1].strip())
    try:   # agua en el perfil (ERA5-Land): complemento, si falla el balance sale igual
        data['profile'] = prof.result(timeout=45)['data']
    except Exception as e:
        data['profile'] = None; data['profile_error'] = type(e).__name__
    pool.shutdown(wait=False)
    return c.envelope(data, ARCHIVE, 'balance de agua y sequía desde 1991', 'Copernicus ERA5 vía Open-Meteo')
