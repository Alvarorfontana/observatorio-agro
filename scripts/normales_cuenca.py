"""Cifras de referencia de la Cuenca del Plata (corre en GitHub Actions, gratis y por partes).

Para cada localidad ribereña:
  - Caudal (GloFAS, Copernicus, 20 años): normal por fecha, crecidas de 2, 5 y 20 años (Gumbel) y máximo con su fecha.
  - Altura (INA, escalas de Prefectura, 20 años): máximo registrado con su fecha.
  - Días de traslado entre localidades vecinas (desfase que maximiza la correlación de los cambios diarios).
Para el río de salida de cada cuenca, con 20 años de lluvia diaria (NASA POWER) en sus subcuencas:
  - cuántos m³/s y cuántos centímetros sube por cada 10 mm de lluvia acumulada en 10 días;
  - cuánta lluvia hizo falta, en la mediana de los casos, para pasar el nivel de alerta y el de evacuación.
Represas de Brasil (ONS): caudal normal por fecha.

Open-Meteo gratis permite 5.000 consultas por hora y 10.000 por día: el script baja hasta MAX_POR_CORRIDA
localidades por corrida y guarda lo bajado en scripts/cache/ (comprimido). La tarea corre todos los días
hasta completar; después, una vez por año.

Uso: python scripts/normales_cuenca.py [salida.json]
"""
import gzip, json, math, os, sys, time
from datetime import date, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cuenca  # noqa: E402

FLOOD = cuenca.FLOOD
POWER_DAILY = 'https://power.larc.nasa.gov/api/temporal/daily/point'
POWER_CLIM = 'https://power.larc.nasa.gov/api/temporal/climatology/point'
Y0, Y1 = 2005, 2024
STEP = 0.05
PAUSE = int(os.environ.get('NORMALES_PAUSA', '380'))
MAX_POR_CORRIDA = int(os.environ.get('NORMALES_MAX', '16'))
CACHE = os.path.join(HERE, 'cache', 'cuenca_series.json.gz')
UA = {'User-Agent': 'DOTS-Campo normales (GitHub Actions)'}


def get(url, params=None, tries=4, timeout=180):
    for i in range(tries):
        r = requests.get(url, params=params, headers=UA, timeout=timeout)
        if r.status_code == 429 and i < tries - 1:
            time.sleep(PAUSE * (i + 1)); continue
        r.raise_for_status()
        return r.json()


def key(d):
    return f'{d.month:02d}-{(d.day // 5) * 5:02d}'


def quant(xs, q):
    xs = sorted(xs); pos = (len(xs) - 1) * q; lo = int(pos); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def dates(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


# ───────────────────────────── caché ─────────────────────────────
def load_cache(path=CACHE):
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            c = json.load(f)
    except (OSError, ValueError):
        c = {}
    for k in ('q', 'cells', 'rain', 'h'):
        c.setdefault(k, {})
    c.setdefault('start', f'{Y0}-01-01')
    return c


def save_cache(c, path=CACHE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        json.dump(c, f, separators=(',', ':'))


# ───────────────────────────── cálculos ─────────────────────────────
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
    """Crecidas de 2, 5 y 20 años (Gumbel por momentos sobre máximos anuales) y el máximo con su fecha."""
    peaks, when = {}, {}
    for t, v in zip(times, values):
        if v is not None and v > peaks.get(t[:4], -1):
            peaks[t[:4]] = v; when[t[:4]] = t
    xs = list(peaks.values())
    if len(xs) < 10:
        return None
    m = sum(xs) / len(xs); sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** .5
    beta = sd * math.sqrt(6) / math.pi; mu = m - 0.5772 * beta
    q = lambda T: mu - beta * math.log(-math.log(1 - 1 / T))
    top = max(peaks, key=peaks.get)
    return {'q2': round(q(2)), 'q5': round(q(5)), 'q20': round(q(20)), 'years': len(xs), 'method': 'Gumbel, máximos anuales',
            'max': round(peaks[top]), 'max_date': when[top]}


def record(times, values):
    best = None
    for t, v in zip(times, values):
        if v is not None and (best is None or v > best[1]):
            best = (t, v)
    return {'value': round(best[1], 2), 'date': best[0]} if best else None


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


def rain_rise(rain, series, response, thresholds=None, window=10, min_rain=20, scale=1.0):
    """Relación lluvia → crecida, como se usa con un pronóstico: "si en los próximos 10 días llueven X mm…".
    rain y series: listas diarias alineadas (mm de la cuenca; m³/s o metros en el río de salida).
    Eventos: el día en que empieza a llover después de 3 días secos, si en los 10 días siguientes caen ≥ `min_rain` mm.
    Subida = máximo de la serie entre `desde` y `10 + hasta` días después, menos el valor del día de inicio.
    Devuelve la subida por cada 10 mm (mediana de cocientes, robusta), el ajuste lineal r, los casos y la
    lluvia mediana de los eventos en que el río cruzó cada umbral."""
    import numpy as np
    P = np.nan_to_num(np.asarray([np.nan if v is None else v for v in rain], float))
    S = np.asarray([np.nan if v is None else v for v in series], float)
    n = min(len(P), len(S)); P, S = P[:n], S[:n]
    lo, hi = int(response[0]), int(response[1])
    F = np.array([P[t:t + window].sum() for t in range(n)])      # lluvia de los próximos 10 días
    xs, ys = [], []
    before = {k: [] for k in (thresholds or {})}
    t = 1
    while t < n - window - hi - 1:
        start = P[t] >= 1 and P[max(0, t - 3):t].sum() < 5      # empieza a llover después de días secos
        if start and F[t] >= min_rain and not np.isnan(S[t]):
            fut = S[t + lo:t + window + hi + 1]
            if not np.isnan(fut).all():
                top = float(np.nanmax(fut))
                xs.append(float(F[t])); ys.append(top - float(S[t]))
                for k, th in (thresholds or {}).items():
                    if th is not None and S[t] < th <= top:
                        before[k].append(float(F[t]))
            t += window                                            # un evento por vez
        else:
            t += 1
    if len(xs) < 15:
        return None
    x, y = np.asarray(xs), np.asarray(ys)
    big = x >= 40
    xb, yb = (x[big], y[big]) if big.sum() >= 8 else (x, y)
    ratio = float(np.median(yb / xb))
    r = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else 0.0
    med = lambda v: round(float(np.median(v))) if len(v) >= 3 else None
    return {'per10mm': round(10 * ratio * scale, 2), 'r': round(r, 2), 'cases': len(xs), 'window_days': window,
            **{f'rain_{k}_mm': med(v) for k, v in before.items()}, **{f'{k}_cases': len(v) for k, v in before.items()}}


# ───────────────────────────── descargas ─────────────────────────────
def pick_cells(stations):
    cand = []
    for st in stations:
        for dy in (-STEP, 0, STEP):
            for dx in (-STEP, 0, STEP):
                cand.append((st['id'], round(st['lat'] + dy, 3), round(st['lon'] + dx, 3)))
    best = {}
    for i in range(0, len(cand), 30):
        part = cand[i:i + 30]
        data = get(FLOOD, {'latitude': ','.join(str(c[1]) for c in part), 'longitude': ','.join(str(c[2]) for c in part),
                           'daily': 'river_discharge', 'past_days': 31, 'forecast_days': 1})
        for (sid, la, lo), resp in zip(part, data if isinstance(data, list) else [data]):
            qv = [v for v in (resp.get('daily') or {}).get('river_discharge') or [] if v is not None]
            m = sum(qv) / len(qv) if qv else -1
            if sid not in best or m > best[sid][2]:
                best[sid] = (la, lo, m)
        time.sleep(5)
    return {sid: {'lat': v[0], 'lon': v[1]} for sid, v in best.items()}


def fetch_station(cell):
    d = get(FLOOD, {'latitude': cell['lat'], 'longitude': cell['lon'], 'daily': 'river_discharge',
                    'start_date': f'{Y0}-01-01', 'end_date': f'{Y1}-12-31'})
    return [None if v is None else round(v) for v in d['daily']['river_discharge']]


def fetch_ina_heights(site):
    """Alturas diarias del INA 2005-2024 (por años, para no pedir de más). Lista alineada con la caché, en cm."""
    t = dates(f'{Y0}-01-01', (date(Y1, 12, 31) - date(Y0, 1, 1)).days + 1)
    idx = {d: i for i, d in enumerate(t)}
    out = [None] * len(t)
    for y in range(Y0, Y1 + 1):
        j = get(cuenca.ina_url('datos', timeStart=f'{y}-01-01', timeEnd=f'{y + 1}-01-01', siteCode=site, varId=2, format='json'), timeout=120)
        for r in j.get('data') or []:
            i = idx.get(str(r.get('timestart', ''))[:10])
            if i is not None and r.get('valor') is not None:
                out[i] = round(100 * float(r['valor']))
        time.sleep(1)
    return out


def fetch_basin_rain(basin):
    series = []
    for la, lo in basin['points']:
        d = get(POWER_DAILY, {'parameters': 'PRECTOTCORR', 'community': 'AG', 'latitude': la, 'longitude': lo,
                              'start': f'{Y0}0101', 'end': f'{Y1}1231', 'format': 'JSON'})
        p = d['properties']['parameter']['PRECTOTCORR']
        series.append([None if (v is None or v < -900) else v for _, v in sorted(p.items())])
        time.sleep(2)
    n = min(len(s) for s in series)
    out = []
    for i in range(n):
        vs = [s[i] for s in series if s[i] is not None]
        out.append(round(10 * sum(vs) / len(vs)) if vs else None)
    return out


def power_rain15(basin):
    months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    per = {m: [] for m in range(1, 13)}
    for la, lo in basin['points']:
        d = get(POWER_CLIM, {'parameters': 'PRECTOTCORR', 'community': 'AG', 'latitude': la, 'longitude': lo, 'format': 'JSON'})
        p = d['properties']['parameter']['PRECTOTCORR']
        for i, m in enumerate(months, 1):
            if p.get(m) is not None and p[m] > -900:
                per[i].append(p[m])
        time.sleep(2)
    return {str(m): round(15 * sum(v) / len(v)) for m, v in per.items() if v}


def dams():
    series = {}
    for y in range(Y0, Y1 + 1):
        r = requests.get(cuenca.ONS_CSV.format(year=y), headers=UA, timeout=180, stream=True)
        if r.status_code != 200:
            continue
        r.encoding = r.encoding or 'utf-8'
        for k, rows in cuenca.parse_ons(r.iter_lines(decode_unicode=True)).items():
            series.setdefault(k, []).extend(rows)
    return {k: {'period': f'{Y0}-{Y1}', 'doy': doy_percentiles([r[0] for r in rows], [r[2] for r in rows])} for k, rows in series.items()}


# ───────────────────────────── armado (sin red) ─────────────────────────────
def basin_rain_mean(cache, basins, n):
    out = []
    for i in range(n):
        vs = [cache['rain'][b['id']][i] for b in basins if i < len(cache['rain'][b['id']]) and cache['rain'][b['id']][i] is not None]
        out.append(sum(vs) / len(vs) / 10 if vs else None)
    return out


def compute(cache):
    n_all = max([len(v) for v in list(cache['q'].values()) + list(cache['h'].values())] or [0])
    t = dates(cache['start'], n_all)
    stations = {}
    for st in cuenca.STATIONS:
        q = cache['q'].get(st['id']); h = cache['h'].get(st['id'])
        if not q and not h:
            continue
        e = {**cache['cells'].get(st['id'], {'lat': st['lat'], 'lon': st['lon']}), 'period': f'{Y0}-{Y1}'}
        if q:
            e['doy'] = doy_percentiles(t[:len(q)], q); e['return_periods'] = gumbel(t[:len(q)], q)
        if h:
            rec = record(t[:len(h)], [None if v is None else v / 100 for v in h])
            if rec:
                e['height_record'] = rec
        stations[st['id']] = e
    lags = {}
    for ch in cuenca.CHAINS:
        for u, d in zip(ch['stations'], ch['stations'][1:]):
            if f'{u}>{d}' not in lags and u in cache['q'] and d in cache['q']:
                n = min(len(cache['q'][u]), len(cache['q'][d]))
                r = lag_days([float('nan') if v is None else v for v in cache['q'][u][:n]],
                             [float('nan') if v is None else v for v in cache['q'][d][:n]])
                if r:
                    lags[f'{u}>{d}'] = r
    rise = {}
    for outlet in sorted({b['outlet'] for b in cuenca.BASINS}):
        bs = [b for b in cuenca.BASINS if b['outlet'] == outlet]
        if not all(b['id'] in cache['rain'] for b in bs):
            continue
        resp = (min(b['response'][0] for b in bs), max(b['response'][1] for b in bs))
        entry = {'basins': [b['id'] for b in bs], 'response': list(resp)}
        if outlet in cache['q']:
            n = len(cache['q'][outlet])
            rp = (stations.get(outlet) or {}).get('return_periods') or {}
            r = rain_rise(basin_rain_mean(cache, bs, n), cache['q'][outlet], resp, {'q5': rp.get('q5'), 'q20': rp.get('q20')})
            if r:
                entry['discharge'] = r
        if outlet in cache['h']:
            n = len(cache['h'][outlet])
            sc, alert, evac, _low = cuenca.INA_SITES.get(outlet, (None, None, None, None))
            r = rain_rise(basin_rain_mean(cache, bs, n), [None if v is None else v / 100 for v in cache['h'][outlet]], resp,
                          {'alert': alert, 'evac': evac})
            if r:
                entry['height'] = r
        if 'discharge' in entry or 'height' in entry:
            rise[outlet] = entry
    return {'stations': stations, 'lags': lags, 'lags_period': f'{Y0}-{Y1}', 'rain_rise': rise}


def main(path):
    prev = {}
    if os.path.exists(path):
        try:
            prev = json.load(open(path, encoding='utf-8'))
        except ValueError:
            prev = {}
    if prev.get('complete') and str(prev.get('updated', ''))[:4] == str(date.today().year) and os.environ.get('NORMALES_FORZAR') != '1':
        print('[normales] completas para este año: nada que hacer.', flush=True)
        return
    cache = load_cache()
    errors = []
    def note(what, e):
        msg = f'{what}: {type(e).__name__} {str(e)[:160]}'
        errors.append(msg); print(f'[normales] {msg}', flush=True)
    if not cache['cells']:
        try:
            cache['cells'] = pick_cells(cuenca.STATIONS); save_cache(cache)
        except Exception as e:
            note('celdas GloFAS', e)
    # alturas del INA (sin límite de consultas): todas las localidades que tienen escala
    for sid, (site, *_r) in cuenca.INA_SITES.items():
        if sid not in cache['h']:
            try:
                cache['h'][sid] = fetch_ina_heights(site); save_cache(cache)
                print(f'[normales] alturas INA {sid}: listas', flush=True)
            except Exception as e:
                note(f'alturas INA {sid}', e)
    # lluvia de las subcuencas (NASA POWER)
    for b in cuenca.BASINS:
        if b['id'] not in cache['rain']:
            try:
                cache['rain'][b['id']] = fetch_basin_rain(b); save_cache(cache)
                print(f'[normales] lluvia {b["name"]}: lista', flush=True)
            except Exception as e:
                note(f'lluvia {b["id"]}', e)
    # caudales GloFAS: hasta MAX_POR_CORRIDA por día (límites gratuitos de Open-Meteo)
    pending = [s for s in cuenca.STATIONS if s['id'] not in cache['q']]
    for st in pending[:MAX_POR_CORRIDA]:
        try:
            cache['q'][st['id']] = fetch_station(cache['cells'].get(st['id'], st)); save_cache(cache)
            print(f'[normales] caudal {st["river"]} · {st["place"]}: listo', flush=True)
        except Exception as e:
            note(f'caudal {st["id"]}', e)
        time.sleep(PAUSE)
    try:
        data = compute(cache)
    except Exception as e:
        note('cálculo', e); data = {'stations': {}, 'lags': {}, 'rain_rise': {}}
    basins = prev.get('basins') or {}
    for b in cuenca.BASINS:
        if b['id'] not in basins:
            try:
                basins[b['id']] = {'rain15_by_month': power_rain15(b), 'source': 'NASA POWER climatología (PRECTOTCORR, mm/día × 15)'}
            except Exception as e:
                note(f'normal de lluvia {b["id"]}', e)
    data['basins'] = basins
    data['dams'] = prev.get('dams') or {}
    if not data['dams']:
        try:
            data['dams'] = dams()
        except Exception as e:
            note('represas', e)
    data['errors'] = errors[:20] + (errors[-20:] if len(errors) > 20 else [])
    data['updated'] = date.today().isoformat()
    data['complete'] = len(cache['q']) == len(cuenca.STATIONS)
    data['progress'] = f"{len(cache['q'])} de {len(cuenca.STATIONS)} localidades con caudal"
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f"[normales] {data['progress']} · {len(data['lags'])} tramos · {len(data['rain_rise'])} relaciones lluvia-crecida", flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'cuenca_normales.json'))
