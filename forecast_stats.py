"""forecast_stats v2.8 — estadística y pronóstico probabilístico del lote.

1. Pronóstico por conjunto a 15 días (Open-Meteo Ensemble API: ECMWF IFS 51 miembros, GFS 31):
   probabilidad diaria de helada, calor extremo y lluvia, con mediana y rango p10-p90.
2. Climatología de 30 años (ERA5): probabilidad mensual de helada, días de calor y lluvia típica.
3. Tendencias: prueba de Mann-Kendall y pendiente de Sen sobre índices anuales.
4. Perspectiva estacional (ECMWF vía Open-Meteo Seasonal): probabilidad de lluvia y temperatura
   bajo / normal / sobre lo normal, contra los terciles de ERA5 1991-2020 del mismo lugar.
Todo en Python puro; cada bloque falla por separado sin inventar datos.
"""
import math, re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import research_connectors as c

ENSEMBLE = 'https://ensemble-api.open-meteo.com/v1/ensemble'
SEASONAL = 'https://seasonal-api.open-meteo.com/v1/seasonal'
ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


# ───────────────────────────── utilidades estadísticas ─────────────────────────────
def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    pos = (len(xs) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def members(block, var):
    """Columnas de un mismo variable: 'var' (control) y 'var_memberNN'."""
    pat = re.compile(rf'^{re.escape(var)}(_member\d+)?$')
    return [v for k, v in block.items() if pat.match(k)]


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def mann_kendall(xs):
    """Devuelve (S, Z, p bilateral) con corrección por empates."""
    x = [v for v in xs if v is not None]
    n = len(x)
    if n < 8:
        return None
    s = sum((1 if x[j] > x[i] else -1 if x[j] < x[i] else 0) for i in range(n - 1) for j in range(i + 1, n))
    counts = {}
    for v in x:
        counts[v] = counts.get(v, 0) + 1
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in counts.values() if t > 1)) / 18
    z = 0.0 if s == 0 else (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var)
    p = 2 * (1 - norm_cdf(abs(z)))
    return s, z, p


def sen_slope(years, xs):
    pts = [(y, v) for y, v in zip(years, xs) if v is not None]
    slopes = [(pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0])
              for i in range(len(pts)) for j in range(i + 1, len(pts)) if pts[j][0] != pts[i][0]]
    return quantile(slopes, 0.5)


# ───────────────────────────── 1. conjunto 15 días ─────────────────────────────
def ensemble_probs(lat, lon):
    params = {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 15,
              'daily': 'temperature_2m_min,temperature_2m_max,precipitation_sum',
              'models': 'ecmwf_ifs025,gfs025'}
    try:
        env = c.external(ENSEMBLE, params)
    except Exception:
        params.pop('models')  # modelo por defecto si los identificadores cambiaron
        env = c.external(ENSEMBLE, params)
    daily = env['data'].get('daily') or {}
    t = daily.get('time') or []
    tn, tx, pr = members(daily, 'temperature_2m_min'), members(daily, 'temperature_2m_max'), members(daily, 'precipitation_sum')
    # con varios modelos Open-Meteo agrega sufijos de modelo: se toman todas las columnas
    if not tn:
        tn = [v for k, v in daily.items() if k.startswith('temperature_2m_min')]
        tx = [v for k, v in daily.items() if k.startswith('temperature_2m_max')]
        pr = [v for k, v in daily.items() if k.startswith('precipitation_sum')]
    if not t or not tn:
        raise ValueError('El pronóstico por conjunto no trajo miembros')
    days = []
    for i, d in enumerate(t):
        a = [m[i] for m in tn if i < len(m) and m[i] is not None]
        b = [m[i] for m in tx if i < len(m) and m[i] is not None]
        r = [m[i] for m in pr if i < len(m) and m[i] is not None]
        if not a:
            continue
        p = lambda xs, f: round(100 * sum(1 for v in xs if f(v)) / len(xs)) if xs else None
        days.append({'date': d, 'members': len(a),
                     'p_frost': p(a, lambda v: v < 0), 'p_frost3': p(a, lambda v: v <= 3),
                     'p_heat35': p(b, lambda v: v >= 35), 'p_rain10': p(r, lambda v: v >= 10), 'p_rain25': p(r, lambda v: v >= 25),
                     'tmin_med': _r(quantile(a, .5)), 'tmin_p10': _r(quantile(a, .1)),
                     'tmax_med': _r(quantile(b, .5)), 'tmax_p90': _r(quantile(b, .9)),
                     'rain_med': _r(quantile(r, .5)), 'rain_p90': _r(quantile(r, .9))})
    week = []
    for m in pr:
        week.append(sum(v for v in m[:7] if v is not None))
    nwk = len(week)
    return {'members': len(tn), 'days': days,
            'week_rain': {'p10': _r(quantile(week, .1)), 'median': _r(quantile(week, .5)), 'p90': _r(quantile(week, .9)),
                          'p_ge20': round(100 * sum(1 for v in week if v >= 20) / nwk) if nwk else None,
                          'p_lt5': round(100 * sum(1 for v in week if v < 5) / nwk) if nwk else None},
            'source': ENSEMBLE}


def _r(v, d=1):
    return None if v is None else round(v, d)


# ───────────────────────────── 2 y 3. climatología y tendencias ─────────────────────────────
def era5_daily(lat, lon, y0=1991, y1=None):
    y1 = y1 or c._now().year - 1
    env = c.external(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': f'{y0}-01-01', 'end_date': f'{y1}-12-31',
                               'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum',
                               'models': 'era5', 'timezone': 'auto'})
    d = env['data'].get('daily') or {}
    rows = []
    for i, day in enumerate(d.get('time') or []):
        rows.append((date.fromisoformat(day), d['temperature_2m_max'][i], d['temperature_2m_min'][i],
                     d['temperature_2m_mean'][i], d['precipitation_sum'][i]))
    if len(rows) < 3650:
        raise ValueError('ERA5 devolvió una serie demasiado corta')
    return rows


def climatology(rows):
    by = {}
    for d, tx, tn, tg, pr in rows:
        k = (d.year, d.month)
        b = by.setdefault(k, {'frost': 0, 'heat': 0, 'rain': 0.0, 'tg': [], 'n': 0})
        b['n'] += 1
        if tn is not None and tn < 0: b['frost'] += 1
        if tx is not None and tx >= 35: b['heat'] += 1
        if pr is not None: b['rain'] += pr
        if tg is not None: b['tg'].append(tg)
    months = []
    for m in range(1, 13):
        ys = [v for (y, mm), v in by.items() if mm == m and v['n'] >= 27]
        if not ys:
            continue
        rain = [v['rain'] for v in ys]; tgm = [sum(v['tg']) / len(v['tg']) for v in ys if v['tg']]
        months.append({'month': m, 'label': MONTHS[m - 1], 'years': len(ys),
                       'p_frost': round(100 * sum(1 for v in ys if v['frost'] > 0) / len(ys)),
                       'frost_days': round(sum(v['frost'] for v in ys) / len(ys), 1),
                       'heat_days': round(sum(v['heat'] for v in ys) / len(ys), 1),
                       'rain_p33': _r(quantile(rain, 1 / 3)), 'rain_med': _r(quantile(rain, .5)), 'rain_p67': _r(quantile(rain, 2 / 3)),
                       'tg_p33': _r(quantile(tgm, 1 / 3)), 'tg_p67': _r(quantile(tgm, 2 / 3))})
    return months


def trends(rows):
    ann = {}
    for d, tx, tn, tg, pr in rows:
        a = ann.setdefault(d.year, {'rain': 0.0, 'frost': 0, 'heat': 0, 'tx': [], 'n': 0})
        a['n'] += 1
        if pr is not None: a['rain'] += pr
        if tn is not None and tn < 0: a['frost'] += 1
        if tx is not None:
            a['tx'].append(tx)
            if tx >= 35: a['heat'] += 1
    years = sorted(y for y, a in ann.items() if a['n'] >= 360)
    series = {'rain': ('Lluvia anual', 'mm'), 'frost': ('Días con helada', 'días'),
              'heat': ('Días con máxima ≥ 35 °C', 'días'), 'tx': ('Máxima media anual', '°C')}
    out = []
    for key, (label, unit) in series.items():
        xs = [(sum(ann[y]['tx']) / len(ann[y]['tx'])) if key == 'tx' else ann[y][key] for y in years]
        mk = mann_kendall(xs)
        slope = sen_slope(years, xs)
        if not mk or slope is None:
            continue
        s, z, p = mk
        sig = p < 0.05
        out.append({'key': key, 'label': label, 'unit': unit, 'per_decade': round(slope * 10, 2 if key == 'tx' else 1),
                    'p_value': round(p, 3), 'significant': sig,
                    'reading': ('aumenta' if slope > 0 else 'disminuye' if slope < 0 else 'estable')
                               + (' (tendencia significativa)' if sig else ' (no significativa: puede ser variabilidad)'),
                    'years': [years[0], years[-1]]})
    return out


# ───────────────────────────── 4. estacional ─────────────────────────────
def seasonal_outlook(lat, lon, clim):
    env = c.external(SEASONAL, {'latitude': lat, 'longitude': lon, 'timezone': 'auto',
                                'daily': 'precipitation_sum,temperature_2m_mean'})
    daily = env['data'].get('daily') or {}
    t = daily.get('time') or []
    pr = members(daily, 'precipitation_sum') or [v for k, v in daily.items() if k.startswith('precipitation_sum')]
    tg = members(daily, 'temperature_2m_mean') or [v for k, v in daily.items() if k.startswith('temperature_2m_mean')]
    if not t or not pr:
        raise ValueError('La perspectiva estacional no trajo miembros')
    cm = {m['month']: m for m in clim}
    import calendar
    idx = {}
    for i, d in enumerate(t):
        y, mth = int(d[:4]), int(d[5:7])
        idx.setdefault((y, mth), []).append(i)
    out = []
    today = c._now().date()
    for (y, mth), ii in sorted(idx.items()):
        if len(ii) < calendar.monthrange(y, mth)[1] - 1 or (y, mth) <= (today.year, today.month):
            continue
        ref = cm.get(mth)
        if not ref:
            continue
        rain_tot = [sum(m[i] for i in ii if m[i] is not None) for m in pr]
        temp_mean = [sum(m[i] for i in ii if m[i] is not None) / len(ii) for m in tg] if tg else []
        def terc(xs, lo, hi):
            n = len(xs)
            if not n or lo is None or hi is None:
                return None
            return {'below': round(100 * sum(1 for v in xs if v < lo) / n),
                    'normal': round(100 * sum(1 for v in xs if lo <= v <= hi) / n),
                    'above': round(100 * sum(1 for v in xs if v > hi) / n)}
        r = terc(rain_tot, ref['rain_p33'], ref['rain_p67']); tt = terc(temp_mean, ref['tg_p33'], ref['tg_p67'])
        def lead(x, names):
            if not x:
                return 'sin dato'
            k = max(x, key=x.get)
            return names[k] if x[k] >= 45 else 'sin señal clara'
        out.append({'period': f'{MONTHS[mth - 1]} {y}', 'members': len(pr),
                    'rain': r, 'rain_median': _r(quantile(rain_tot, .5)), 'rain_normal': ref['rain_med'],
                    'rain_reading': lead(r, {'below': 'más seco que lo normal', 'normal': 'cerca de lo normal', 'above': 'más lluvioso que lo normal'}),
                    'temp': tt, 'temp_reading': lead(tt, {'below': 'más fresco que lo normal', 'normal': 'cerca de lo normal', 'above': 'más cálido que lo normal'})})
        if len(out) >= 5:
            break
    return out


def analyze(lat, lon):
    out, errors = {}, {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_ens = pool.submit(ensemble_probs, lat, lon)
        f_era = pool.submit(era5_daily, lat, lon)
        try:
            rows = f_era.result()
            out['climatology'] = climatology(rows)
            out['trends'] = trends(rows)
        except Exception as e:
            errors['climatology'] = type(e).__name__
        try:
            out['ensemble'] = f_ens.result()
        except Exception as e:
            errors['ensemble'] = type(e).__name__
    if out.get('climatology'):
        try:
            out['seasonal'] = seasonal_outlook(lat, lon, out['climatology'])
        except Exception as e:
            errors['seasonal'] = type(e).__name__
    ok = bool(out)
    out['errors'] = errors
    out['method'] = ('Probabilidad = porcentaje de miembros del conjunto que cumplen la condición. Climatología y terciles: ERA5 1991-'
                     f'{c._now().year - 1} en el punto del lote (~25 km). Tendencias: Mann-Kendall y pendiente de Sen, significativas si p < 0,05.')
    return c.envelope(out, ENSEMBLE, 'estadística y pronóstico probabilístico', 'ECMWF · NOAA · Copernicus ERA5 vía Open-Meteo',
                      'recibido' if ok else 'sin dato', None if ok else 'Ninguna fuente estadística respondió')
