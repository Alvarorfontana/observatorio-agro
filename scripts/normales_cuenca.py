"""Normales de la Cuenca del Plata para el panel regional (corre en GitHub Actions, gratis).

  - Ríos: para cada estación elige la celda GloFAS del cauce principal (la de mayor caudal en un
    3x3 de ~5 km alrededor del punto) y calcula percentiles de caudal 2001-2020 por ventana de
    5 días del año (con ±7 días de margen).
  - Tiempos de traslado: desfase en días entre estaciones encadenadas que maximiza la correlación
    de los cambios diarios de caudal (20 años), y crecidas de 2, 5 y 20 años (Gumbel) para el peligro.
  - Cabeceras: lluvia normal de 15 días por mes, con la climatología de NASA POWER en cada punto.
Resultado: data/cuenca_normales.json (chico, va con el código). Respeta los límites de Open-Meteo:
pide 20 años por estación y espera ~6 minutos entre estaciones (tarda ~1 hora).

Uso: python scripts/normales_cuenca.py [salida.json]
"""
import json, os, sys, time
from datetime import date, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cuenca  # noqa: E402

FLOOD = cuenca.FLOOD
POWER_CLIM = 'https://power.larc.nasa.gov/api/temporal/climatology/point'
Y0, Y1 = 2001, 2020
STEP = 0.05
PAUSE = int(os.environ.get('NORMALES_PAUSA', '380'))   # menos de 5000 consultas por hora
UA = {'User-Agent': 'DOTS-Campo normales (GitHub Actions)'}


def get(url, params, tries=4):
    for i in range(tries):
        r = requests.get(url, params=params, headers=UA, timeout=120)
        if r.status_code == 429 and i < tries - 1:
            time.sleep(PAUSE * (i + 1)); continue
        r.raise_for_status()
        return r.json()


def key(d):
    return f'{d.month:02d}-{(d.day // 5) * 5:02d}'


def pick_cells():
    """Celda de mayor caudal medio (últimos 30 días) en un 3x3 alrededor de cada estación."""
    cand = []
    for st in cuenca.STATIONS:
        for dy in (-STEP, 0, STEP):
            for dx in (-STEP, 0, STEP):
                cand.append((st['id'], round(st['lat'] + dy, 3), round(st['lon'] + dx, 3)))
    data = get(FLOOD, {'latitude': ','.join(str(c[1]) for c in cand), 'longitude': ','.join(str(c[2]) for c in cand),
                       'daily': 'river_discharge', 'past_days': 31, 'forecast_days': 1})
    best = {}
    for (sid, la, lo), resp in zip(cand, data if isinstance(data, list) else [data]):
        q = [v for v in (resp.get('daily') or {}).get('river_discharge') or [] if v is not None]
        m = sum(q) / len(q) if q else -1
        if sid not in best or m > best[sid][2]:
            best[sid] = (la, lo, m)
    return {sid: {'lat': v[0], 'lon': v[1]} for sid, v in best.items()}


def quant(xs, q):
    xs = sorted(xs); pos = (len(xs) - 1) * q; lo = int(pos); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def doy_percentiles(times, values):
    """{'MM-DD': {min, p10, p25, p50, p75, p90, p97, max}} con ventana de ±7 días alrededor de cada clave."""
    by_day = {}
    for t, v in zip(times, values):
        if v is not None:
            by_day.setdefault(t[5:], []).append(v)
    out = {}
    ref = date(2001, 1, 1)
    for n in range(365):
        d = ref + timedelta(days=n)
        k = key(d)
        if k in out:
            continue
        mid = date(2001, d.month, min(d.day + 2, 28))
        vals = []
        for off in range(-7, 8):
            vals += by_day.get((mid + timedelta(days=off)).strftime('%m-%d'), [])
        if len(vals) >= 30:
            out[k] = {'min': round(min(vals)), **{f'p{p}': round(quant(vals, p / 100)) for p in (10, 25, 50, 75, 90, 97)},
                      'max': round(max(vals))}
    return out


def gumbel(times, values):
    """Crecidas de 2, 5 y 20 años con Gumbel (momentos) sobre los máximos anuales."""
    import math
    peaks = {}
    for t, v in zip(times, values):
        if v is not None:
            peaks[t[:4]] = max(peaks.get(t[:4], v), v)
    xs = list(peaks.values())
    if len(xs) < 10:
        return None
    m = sum(xs) / len(xs); sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** .5
    beta = sd * math.sqrt(6) / math.pi; mu = m - 0.5772 * beta
    q = lambda T: mu - beta * math.log(-math.log(1 - 1 / T))
    return {'q2': round(q(2)), 'q5': round(q(5)), 'q20': round(q(20)), 'years': len(xs), 'method': 'Gumbel, máximos anuales'}


def lag_days(up, down, max_lag=30):
    """Desfase (días) que maximiza la correlación entre los cambios diarios (suavizados 3 días) de dos estaciones."""
    import numpy as np
    a = np.asarray(up, float); b = np.asarray(down, float)
    k = np.ones(3) / 3
    da = np.diff(np.convolve(a, k, 'same')); db = np.diff(np.convolve(b, k, 'same'))
    best = (None, -2.0)
    for L in range(0, max_lag + 1):
        x = da[:len(da) - L]; y = db[L:]
        ok = ~(np.isnan(x) | np.isnan(y))
        if ok.sum() < 365:
            continue
        r = float(np.corrcoef(x[ok], y[ok])[0, 1])
        if r > best[1]:
            best = (L, r)
    if best[0] is None:
        return None
    return {'days': best[0], 'corr': round(best[1], 2)}


def lags(series):
    out = {}
    for ch in cuenca.CHAINS:
        for u, d in zip(ch['stations'], ch['stations'][1:]):
            if f'{u}>{d}' in out or u not in series or d not in series:
                continue
            tu, vu = series[u]; td, vd = series[d]
            common = sorted(set(tu) & set(td))
            iu = dict(zip(tu, vu)); idd = dict(zip(td, vd))
            r = lag_days([iu[t] if iu[t] is not None else float('nan') for t in common],
                         [idd[t] if idd[t] is not None else float('nan') for t in common])
            if r:
                out[f'{u}>{d}'] = r
                print(f'[normales] {u} → {d}: {r["days"]} días (r={r["corr"]})', flush=True)
    return out


def rivers(cells, series=None):
    out = {}
    for st in cuenca.STATIONS:
        cell = cells.get(st['id'], {'lat': st['lat'], 'lon': st['lon']})
        times, vals = [], []
        for a, b in ((Y0, Y1),):   # 20 años en un pedido (~520 de las 600 consultas por minuto de Open-Meteo)
            d = get(FLOOD, {'latitude': cell['lat'], 'longitude': cell['lon'], 'daily': 'river_discharge',
                            'start_date': f'{a}-01-01', 'end_date': f'{b}-12-31'})
            times += d['daily']['time']; vals += d['daily']['river_discharge']
            time.sleep(PAUSE)
        out[st['id']] = {**cell, 'period': f'{Y0}-{Y1}', 'doy': doy_percentiles(times, vals), 'return_periods': gumbel(times, vals)}
        if series is not None:
            series[st['id']] = (times, vals)
        print(f'[normales] {st["river"]} · {st["place"]}: {len(out[st["id"]]["doy"])} ventanas', flush=True)
    return out


MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']


def basins():
    out = {}
    for b in cuenca.BASINS:
        per_month = {m: [] for m in range(1, 13)}
        for la, lo in b['points']:
            d = get(POWER_CLIM, {'parameters': 'PRECTOTCORR', 'community': 'AG', 'latitude': la, 'longitude': lo, 'format': 'JSON'})
            p = d['properties']['parameter']['PRECTOTCORR']
            for i, m in enumerate(MONTHS, 1):
                if p.get(m) is not None and p[m] > -900:
                    per_month[i].append(p[m])
            time.sleep(2)
        out[b['id']] = {'rain15_by_month': {str(m): round(15 * sum(v) / len(v)) for m, v in per_month.items() if v},
                        'source': 'NASA POWER climatología (PRECTOTCORR, mm/día × 15)'}
        print(f'[normales] {b["name"]}: listo', flush=True)
    return out


def dams():
    """Percentiles del caudal defluente por ventana del año, 2001-2020, desde los CSV anuales del ONS."""
    series = {}
    for y in range(Y0, Y1 + 1):
        r = requests.get(cuenca.ONS_CSV.format(year=y), headers=UA, timeout=180, stream=True)
        if r.status_code != 200:
            print(f'[normales] ONS {y}: HTTP {r.status_code}', flush=True); continue
        r.encoding = r.encoding or 'utf-8'
        for k, rows in cuenca.parse_ons(r.iter_lines(decode_unicode=True)).items():
            series.setdefault(k, []).extend(rows)
    out = {}
    for k, rows in series.items():
        t = [r[0] for r in rows]; v = [r[2] for r in rows]
        out[k] = {'period': f'{Y0}-{Y1}', 'doy': doy_percentiles(t, v)}
        print(f'[normales] represa {k}: {len(rows)} días', flush=True)
    return out


def main(path):
    cells = pick_cells()
    series = {}
    stations = rivers(cells, series)
    data = {'updated': date.today().isoformat(), 'stations': stations, 'lags': lags(series), 'lags_period': f'{Y0}-{Y1}',
            'basins': basins(), 'dams': dams()}
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f'[normales] guardado {path}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'cuenca_normales.json'))
