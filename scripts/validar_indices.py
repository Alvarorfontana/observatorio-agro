"""Contrasta los cálculos propios de DOTS con librerías científicas de referencia (corre en GitHub Actions).

- Índices agroclimáticos (climate_indices.py, Python puro para que la web sea liviana) contra xclim (Ouranosinc).
- SPEI log-logístico (water_balance.py) contra el SPEI de climate_indices (monocongo), que ajusta una Pearson III:
  no tienen que dar idénticos, pero deben ir juntos (correlación alta y casi siempre la misma clase de sequía).
Usa 35 años de clima diario sintético, fijo (semilla) y con estaciones del hemisferio sur.
Uso: python scripts/validar_indices.py   (sale con error si algo no coincide)
"""
import importlib.util
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path = [p for p in sys.path if os.path.abspath(p or '.') not in (ROOT, HERE)]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
import xclim.indices as xi  # noqa: E402
from climate_indices import compute, indices  # noqa: E402  (paquete de PyPI, no el módulo propio)
import logging  # noqa: E402
logging.disable(logging.INFO)

sys.path.insert(0, ROOT)


def local(name, alias):
    spec = importlib.util.spec_from_file_location(alias, os.path.join(ROOT, f'{name}.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dci = local('climate_indices', 'dots_climate_indices')
wb = local('water_balance', 'dots_water_balance')


def synthetic(seed=7, start='1991-01-01', end='2025-12-31'):
    rnd = random.Random(seed)
    days = pd.date_range(start, end, freq='D')
    rows = []
    for d in days:
        s = math.cos(2 * math.pi * (d.dayofyear - 15) / 365.25)          # 1 en enero (verano austral)
        tg = 17 + 9 * s + rnd.gauss(0, 3)
        amp = 6 + rnd.random() * 6
        pr = 0.0 if rnd.random() < 0.72 - 0.12 * s else round(rnd.expovariate(1 / (9 + 6 * s)), 1)
        et0 = max(0.3, 3.2 + 2.6 * s + rnd.gauss(0, 0.8))
        rows.append((d.strftime('%Y-%m-%d'), round(tg + amp / 2, 1), round(tg - amp / 2, 1), round(tg, 1), pr, round(et0, 2)))
    return rows


def da(vals, times, units):
    return xr.DataArray(np.array(vals, dtype=float), coords={'time': times}, dims='time', attrs={'units': units})


def check_indices(rows):
    times = pd.DatetimeIndex([r[0] for r in rows])
    tx, tn, tg, pr = (da([r[i] for r in rows], times, 'degC') for i in (1, 2, 3)), None, None, None
    tx, tn, tg = list(tx)
    pr = da([r[4] for r in rows], times, 'mm/d')
    ref = {
        'frost_days': xi.frost_days(tn, thresh='0 degC'),
        'tx30': xi.tx_days_above(tx, thresh='30 degC', op='>'),
        'tx35': xi.tx_days_above(tx, thresh='35 degC', op='>='),
        'heat_waves': xi.hot_spell_frequency(tx, thresh='35 degC', window=3, op='>='),
        'tropical_nights': xi.tn_days_above(tn, thresh='20 degC', op='>'),
        'gdd10': xi.growing_degree_days(tg, thresh='10 degC'),
        'wetdays': xi.wetdays(pr, thresh='1 mm/d', op='>='),
        'r20mm': xi.wetdays(pr, thresh='20 mm/d', op='>='),
        'rx1day': xi.max_1day_precipitation_amount(pr),
        'rx5day': xi.max_n_day_precipitation_amount(pr, window=5),
        'cdd': xi.maximum_consecutive_dry_days(pr, thresh='1 mm/d'),
        'cwd': xi.maximum_consecutive_wet_days(pr, thresh='1 mm/d'),
        'sdii': xi.daily_pr_intensity(pr, thresh='1 mm/d'),
    }
    daily = {'time': [r[0] for r in rows], 'temperature_2m_max': [r[1] for r in rows], 'temperature_2m_min': [r[2] for r in rows],
             'temperature_2m_mean': [r[3] for r in rows], 'precipitation_sum': [r[4] for r in rows]}
    ours = {y: dci.year_indices(v) for y, v in dci.split_years(daily).items()}
    roll5 = pr.rolling(time=5).sum()
    bad, notes = [], []
    for key, arr in ref.items():
        vals = arr.values
        years = pd.DatetimeIndex(arr['time'].values).year
        for y, v in zip(years, vals):
            mine = ours[y][key]
            tol = 0.15 if key in ('gdd10', 'rx1day', 'rx5day', 'sdii') else 0
            if mine is None or abs(float(mine) - float(v)) > tol + 1e-6 * abs(float(v)):
                if key == 'rx5day':   # xclim suma ventanas que empiezan en diciembre del año anterior; DOTS no cruza el año
                    yr = roll5.sel(time=str(y))
                    if pd.Timestamp(yr.idxmax().values).dayofyear <= 4:
                        notes.append(f'{key} {y}: la racha de xclim cruza el año')
                        continue
                bad.append(f'{key} {y}: DOTS {mine} · xclim {round(float(v), 2)}')
    print(f'Índices: {len(ref)} indicadores × {len(ours)} años contra xclim; {len(bad)} diferencias'
          f'{f" ({len(notes)} por convención de fin de año en rx5day)" if notes else ""}.')
    for b in bad[:20]:
        print('  ', b)
    return not bad


def check_spei(rows, scale=3):
    daily = {'time': [r[0] for r in rows], 'precipitation_sum': [r[4] for r in rows], 'et0_fao_evapotranspiration': [r[5] for r in rows]}
    mon = wb.monthly(daily)
    keys = sorted(mon)
    p = np.array([mon[k][0] for k in keys]); e = np.array([mon[k][1] for k in keys])
    ref = indices.spei(p, e, scale, indices.Distribution.pearson, compute.Periodicity.monthly, keys[0][0], 1991, 2020)
    bal = {k: mon[k][0] - mon[k][1] for k in keys}

    def acc(i):
        return None if i < scale - 1 else sum(bal[keys[j]] for j in range(i - scale + 1, i + 1))

    ours = []
    for i, k in enumerate(keys):
        cal = [acc(j) for j, kk in enumerate(keys) if kk[1] == k[1] and 1991 <= kk[0] <= 2020]
        ours.append(wb.standardize(acc(i), cal))
    pairs = [(a, b) for a, b in zip(ours, ref) if a is not None and b is not None and not math.isnan(b)]
    a = np.array([x for x, _ in pairs]); b = np.array([y for _, y in pairs])
    r = float(np.corrcoef(a, b)[0, 1])
    same = float(np.mean([wb.classify(x) == wb.classify(y) for x, y in pairs]))
    print(f'SPEI-{scale}: {len(pairs)} meses; correlación con climate_indices {r:.3f}; misma clase {same:.0%}.')
    return r >= 0.97 and same >= 0.85


if __name__ == '__main__':
    rows = synthetic()
    ok = check_indices(rows)
    ok = all([check_spei(rows, n) for n in (1, 3, 6, 12)]) and ok
    sys.exit(0 if ok else 1)
