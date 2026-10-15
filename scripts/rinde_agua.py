"""Rinde por agua de maíz y soja con AquaCrop (FAO), para localidades agrícolas del monitor de Sudamérica.

Corre en GitHub Actions (la web sólo lee data/rinde_agua.json). Para cada localidad y campaña (julio a junio):
  - simula el cultivo en secano y con riego completo (potencial sin falta de agua) y guarda el cociente
    secano / potencial: qué parte del rinde posible permitió el agua de esa campaña. Es un índice relativo,
    no una estimación de cosecha: los parámetros del cultivo son los de referencia de la FAO, sin calibrar por lote;
  - para la campaña en curso arma 30 escenarios: lo observado (ERA5) y el pronóstico de 16 días, completados con
    el clima de cada campaña 1991-2020 desde ahí hasta el final. El resultado es un rango (percentiles 10, 50 y 90)
    y la probabilidad de que el índice termine debajo, cerca o encima de lo normal (terciles 1991-2020).
Clima: ERA5 diario (Copernicus) y pronóstico de Open-Meteo. Suelo: franco limoso (loess pampeano) para todas.
Retoma lo que falte si se corta y guarda el clima diario en scripts/cache/rinde/ (rama datos).
Uso: python scripts/rinde_agua.py [salida.json]
"""
import gzip
import json
import os
import sys
import time
from datetime import date, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import enso_sa  # noqa: E402

PAUSE = float(os.environ.get('RINDE_PAUSE', '300'))
CACHE = os.path.join(HERE, 'cache', 'rinde')
VARS = ['temperature_2m_max', 'temperature_2m_min', 'precipitation_sum', 'et0_fao_evapotranspiration']
PLACES = ['reconquista', 'resistencia', 'santa-fe', 'parana', 'gualeguaychu', 'rosario', 'pergamino', 'junin', 'tandil',
          'santa-rosa', 'cordoba', 'rio-cuarto', 'santiago-del-estero', 'tucuman', 'salto-uy', 'encarnacion',
          'passo-fundo', 'santa-maria', 'londrina']
CROPS = {'maiz': ('Maize', '10/01', 'Maíz de primera, siembra 1 de octubre'),
         'soja': ('Soybean', '11/15', 'Soja de primera, siembra 15 de noviembre')}
SOIL = 'SiltLoam'
METHOD = ('Para cada campaña (julio a junio) se simula el cultivo con AquaCrop en secano y con riego completo; el índice es '
          'el cociente entre ambos: qué parte del rinde posible permitió el agua. Es relativo, no una estimación de cosecha: '
          'los parámetros del cultivo son los de referencia de la FAO, sin calibrar por lote. La campaña en curso combina lo '
          'observado (ERA5) y el pronóstico de 16 días con el clima de cada campaña 1991-2020 para el resto: 30 escenarios, '
          'resumidos en los percentiles 10, 50 y 90 y en la probabilidad de terminar debajo, cerca o encima de lo normal '
          '(terciles 1991-2020).')
NORMAL = (1991, 2020)


def season_of(d):
    return d.year if d.month >= 7 else d.year - 1


def get(url, params):
    for i in range(6):
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException:
            time.sleep(60); continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(180 * (i + 1)); continue
        return r if r.ok else None
    return None


def load_cache(pid):
    try:
        with gzip.open(os.path.join(CACHE, f'{pid}.json.gz'), 'rt', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_cache(pid, d):
    os.makedirs(CACHE, exist_ok=True)
    with gzip.open(os.path.join(CACHE, f'{pid}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump(d, f, separators=(',', ':'))


def history(pid, lat, lon, end):
    """Clima diario desde 1991-07-01 hasta `end` (ERA5), con caché incremental. Devuelve (dict, consultó_red)."""
    d = load_cache(pid)
    start = '1991-07-01'
    if d and d.get('time'):
        last = date.fromisoformat(d['time'][-1])
        if last >= end - timedelta(days=1):
            return d, False
        start = (last + timedelta(days=1)).isoformat()
    r = get('https://archive-api.open-meteo.com/v1/archive', {'latitude': lat, 'longitude': lon, 'start_date': start,
            'end_date': end.isoformat(), 'daily': ','.join(VARS), 'models': 'era5', 'timezone': 'UTC'})
    if r is None:
        return d, True
    new = r.json().get('daily') or {}
    if not d:
        d = {'time': [], **{v: [] for v in VARS}}
    d['time'] += new.get('time') or []
    for v in VARS:
        d[v] += [None if x is None else round(x, 1) for x in (new.get(v) or [])]
    # ERA5 recién publicado puede venir incompleto: se descartan los días finales sin dato
    while d['time'] and any(d[v][-1] is None for v in VARS):
        for k in ['time'] + VARS:
            d[k].pop()
    save_cache(pid, d)
    return d, True


def forecast(lat, lon):
    r = get('https://api.open-meteo.com/v1/forecast', {'latitude': lat, 'longitude': lon, 'daily': ','.join(VARS),
            'forecast_days': 16, 'past_days': 10, 'timezone': 'UTC'})
    return (r.json().get('daily') or {}) if r is not None else {}


def frame(rows):
    import pandas as pd
    df = pd.DataFrame(rows, columns=['Date', 'MaxTemp', 'MinTemp', 'Precipitation', 'ReferenceET'])
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date').asfreq('D').interpolate(limit_direction='both').reset_index()
    df['MinTemp'] = df[['MinTemp', 'MaxTemp']].min(axis=1)
    df['ReferenceET'] = df['ReferenceET'].clip(lower=0.1)
    df['Precipitation'] = df['Precipitation'].clip(lower=0)
    return df[['MinTemp', 'MaxTemp', 'Precipitation', 'ReferenceET', 'Date']]


def by_season(d):
    out = {}
    for i, t in enumerate(d['time']):
        s = season_of(date.fromisoformat(t))
        out.setdefault(s, []).append((t, *(d[v][i] for v in VARS)))
    return out


def simulate(rows, season, crop):
    from aquacrop import AquaCropModel, Crop, InitialWaterContent, IrrigationManagement, Soil
    name, planting, _ = CROPS[crop]
    w = frame(rows)
    res = []
    for irr in (IrrigationManagement(irrigation_method=0), IrrigationManagement(irrigation_method=1, SMT=[70] * 4)):
        m = AquaCropModel(f'{season}/07/01', f'{season + 1}/06/30', w, Soil(SOIL), Crop(name, planting_date=planting),
                          InitialWaterContent(wc_type='Pct', value=[50]), irrigation_management=irr)
        m.run_model(till_termination=True)
        res.append(float(m.get_simulation_results()['Dry yield (tonne/ha)'].iloc[0]))
    rainfed, potential = res
    return round(rainfed / potential, 3) if potential > 0.1 else None


def pct(xs, q):
    xs = sorted(xs)
    k = q * (len(xs) - 1); lo = int(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def outlook(hist, obs_rows, season, crop):
    """30 escenarios: lo observado + pronóstico, completado con cada campaña 1991-2020."""
    first = date(season, 7, 1)
    have = {r[0] for r in obs_rows}
    members = []
    for a in range(NORMAL[0], NORMAL[1] + 1):
        analog = hist.get(a) or []
        if len(analog) < 360:
            continue
        rows = list(obs_rows)
        k = len(rows)
        day = first + timedelta(days=k)
        while day <= date(season + 1, 6, 30):
            src = analog[min(k, len(analog) - 1)]
            if day.isoformat() not in have:
                rows.append((day.isoformat(), *src[1:]))
            k += 1; day += timedelta(days=1)
        r = simulate(rows, season, crop)
        if r is not None:
            members.append(r)
    return members


def place(pid, name, country, lat, lon, prev, today):
    end = today - timedelta(days=6)
    d, net = history(pid, lat, lon, end)
    if not d or len(d['time']) < 365 * 25:
        return prev, net
    hist = by_season(d)
    cur = season_of(today)
    fc = forecast(lat, lon)
    obs = [r for r in hist.get(cur, [])]
    known = {r[0] for r in obs}
    for i, t in enumerate(fc.get('time') or []):
        vals = [fc.get(v, [None])[i] for v in VARS]
        if t not in known and t >= f'{cur}-07-01' and all(v is not None for v in vals):
            obs.append((t, *vals)); known.add(t)
    obs.sort()
    out = {'name': name, 'country': country, 'lat': lat, 'lon': lon, 'obs_until': end.isoformat(),
           'forecast_until': obs[-1][0] if obs else None}
    for crop in CROPS:
        ph = dict(((prev or {}).get(crop) or {}).get('history') or {})
        for s in sorted(hist):
            if s < cur and str(s) not in ph and len(hist[s]) >= 360:
                ph[str(s)] = simulate(hist[s], s, crop)
        normal = [v for s, v in ph.items() if NORMAL[0] <= int(s) <= NORMAL[1] and v is not None]
        if len(normal) < 20:
            continue
        t1, t2, med = pct(normal, 1 / 3), pct(normal, 2 / 3), pct(normal, 0.5)
        members = outlook(hist, obs, cur, crop)
        last = max((int(s) for s, v in ph.items() if v is not None), default=None)
        o = None
        if len(members) >= 20:
            n = len(members)
            o = {'p10': round(pct(members, .1), 3), 'p50': round(pct(members, .5), 3), 'p90': round(pct(members, .9), 3),
                 'below': round(sum(m < t1 for m in members) / n, 2), 'near': round(sum(t1 <= m <= t2 for m in members) / n, 2),
                 'above': round(sum(m > t2 for m in members) / n, 2), 'members': n,
                 'vs_normal_pct': round(100 * (pct(members, .5) / med - 1)) if med else None}
        out[crop] = {'history': ph, 'normal': {'p33': round(t1, 3), 'p50': round(med, 3), 'p67': round(t2, 3)},
                     'last_season': {'season': f'{last}/{str(last + 1)[-2:]}', 'ratio': ph[str(last)]} if last else None,
                     'outlook': o}
    return out, net


def main(out_path):
    try:
        res = json.load(open(out_path, encoding='utf-8'))
    except (OSError, ValueError):
        res = {}
    places = res.get('places') or {}
    today = date.today()
    cur = season_of(today)
    lookup = {p[0]: p for p in enso_sa.PLACES}
    for pid in PLACES:
        if pid not in lookup:
            continue
        _, name, country, lat, lon = lookup[pid]
        if (places.get(pid) or {}).get('obs_until') == (today - timedelta(days=6)).isoformat():
            continue
        try:
            row, net = place(pid, name, country, lat, lon, places.get(pid), today)
        except Exception as e:   # una localidad que falla no frena a las demás
            print(f'{name}: error {type(e).__name__}: {e}', flush=True); continue
        if row:
            places[pid] = row
            mz = (row.get('maiz') or {}).get('outlook') or {}
            print(f"{name}: maíz p50 {mz.get('p50')} (abajo {mz.get('below')})", flush=True)
        res = {'updated': today.isoformat(), 'season': f'{cur}/{str(cur + 1)[-2:]}', 'soil': 'Franco limoso',
               'crops': {k: v[2] for k, v in CROPS.items()}, 'normal_period': f'{NORMAL[0]}-{NORMAL[1]}',
               'method': METHOD,
               'source': 'AquaCrop-OSPy (FAO) · Copernicus ERA5 y pronóstico vía Open-Meteo', 'places': places}
        json.dump(res, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        if net:
            time.sleep(PAUSE)
    print(f"{sum(1 for p in places.values() if (p.get('maiz') or {}).get('outlook'))} localidades con escenario de maíz.")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('data', 'rinde_agua.json'))
