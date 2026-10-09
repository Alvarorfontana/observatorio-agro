"""climate_indices v2.2 — índices agroclimáticos por lote y teleconexiones NOAA PSL.

Índices: se calculan en Python puro sobre ERA5 diario (Open-Meteo Archive), con la
definición y el nombre de los indicadores de xclim (https://github.com/Ouranosinc/xclim,
Apache-2.0) / ETCCDI. No se instala xclim: arrastra xarray, dask y numba y no aporta
nada para series de un punto.

Teleconexiones: archivos mensuales de NOAA PSL (https://psl.noaa.gov/data/climateindices/list/).
Formato: línea "año_inicio año_fin", luego "año v1..v12", luego el valor faltante.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import research_connectors as c

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'

# (clave, nombre xclim/ETCCDI, etiqueta, unidad, descripción)
INDICES = [
    ('frost_days', 'frost_days', 'Días con helada', 'días', 'Mínima < 0 °C'),
    ('first_frost', 'first_day_tn_below', 'Primera helada', 'fecha', 'Primer día con mínima < 0 °C'),
    ('last_frost', 'last_day_tn_below', 'Última helada', 'fecha', 'Último día con mínima < 0 °C'),
    ('tx30', 'tx_days_above(30)', 'Días con máxima > 30 °C', 'días', 'Calor de manejo para el rodeo'),
    ('tx35', 'tx_days_above(35)', 'Días con máxima ≥ 35 °C', 'días', 'Calor extremo'),
    ('heat_waves', 'heat_wave_frequency(tx≥35, 3 días)', 'Olas de calor', 'eventos', '3 o más días seguidos con máxima ≥ 35 °C'),
    ('tropical_nights', 'tropical_nights', 'Noches tropicales', 'días', 'Mínima > 20 °C: el animal no recupera de noche'),
    ('gdd10', 'growing_degree_days(10)', 'Grados día base 10', '°C·día', 'Suma de (media − 10) cuando es positiva'),
    ('prcptot', 'prcptot', 'Lluvia anual', 'mm', 'Suma de días con lluvia ≥ 1 mm'),
    ('wetdays', 'wetdays(1mm)', 'Días de lluvia', 'días', 'Lluvia ≥ 1 mm'),
    ('r20mm', 'wetdays(20mm)', 'Días de lluvia intensa', 'días', 'Lluvia ≥ 20 mm'),
    ('rx1day', 'max_1day_precipitation_amount', 'Máxima lluvia en 1 día', 'mm', ''),
    ('rx5day', 'max_n_day_precipitation_amount(5)', 'Máxima lluvia en 5 días', 'mm', 'Riesgo de anegamiento'),
    ('cdd', 'maximum_consecutive_dry_days', 'Racha seca más larga', 'días', 'Días seguidos con lluvia < 1 mm'),
    ('cwd', 'maximum_consecutive_wet_days', 'Racha húmeda más larga', 'días', 'Días seguidos con lluvia ≥ 1 mm'),
    ('sdii', 'daily_pr_intensity', 'Intensidad de lluvia', 'mm/día', 'Lluvia anual / días de lluvia'),
]
NUMERIC = [k for k, *_ in INDICES if k not in ('first_frost', 'last_frost')]


def _run_max(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def _events(flags, n):
    ev = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        if cur == n:
            ev += 1
    return ev


def year_indices(days):
    """days: lista de dicts {date, tx, tn, tg, pr} de UN año. None = faltante."""
    tx = [d['tx'] for d in days]; tn = [d['tn'] for d in days]
    tg = [d['tg'] for d in days]; pr = [d['pr'] for d in days]
    ok = lambda xs: [x for x in xs if x is not None]
    frost = [d['date'] for d in days if d['tn'] is not None and d['tn'] < 0]
    wet = [p for p in ok(pr) if p >= 1]
    rx5 = max((sum(ok(pr[i:i + 5])) for i in range(max(len(pr) - 4, 1))), default=None)
    out = {
        'frost_days': len(frost),
        'first_frost': frost[0] if frost else None,
        'last_frost': frost[-1] if frost else None,
        'tx30': sum(1 for x in ok(tx) if x > 30),
        'tx35': sum(1 for x in ok(tx) if x >= 35),
        'heat_waves': _events([x is not None and x >= 35 for x in tx], 3),
        'tropical_nights': sum(1 for x in ok(tn) if x > 20),
        'gdd10': round(sum(max(x - 10, 0) for x in ok(tg)), 1),
        'prcptot': round(sum(wet), 1),
        'wetdays': len(wet),
        'r20mm': sum(1 for p in ok(pr) if p >= 20),
        'rx1day': round(max(ok(pr)), 1) if ok(pr) else None,
        'rx5day': round(rx5, 1) if rx5 is not None else None,
        'cdd': _run_max([p is not None and p < 1 for p in pr]),
        'cwd': _run_max([p is not None and p >= 1 for p in pr]),
        'sdii': round(sum(wet) / len(wet), 1) if wet else 0.0,
    }
    out['days'] = len(days); out['missing'] = sum(1 for d in days if d['tx'] is None or d['pr'] is None)
    return out


def split_years(daily):
    t = daily.get('time') or []
    cols = {k: daily.get(v) or [None] * len(t) for k, v in
            (('tx', 'temperature_2m_max'), ('tn', 'temperature_2m_min'),
             ('tg', 'temperature_2m_mean'), ('pr', 'precipitation_sum'))}
    years = {}
    for i, d in enumerate(t):
        years.setdefault(int(d[:4]), []).append({'date': d, **{k: cols[k][i] for k in cols}})
    return years


def agro_indices(lat, lon, years=10):
    years = int(years)
    if not 3 <= years <= 30:
        raise ValueError('Años fuera de rango (3-30)')
    end = c._now().year - 1
    env = c.external(ARCHIVE, {'latitude': lat, 'longitude': lon,
                               'start_date': f'{end - years + 1}-01-01', 'end_date': f'{end}-12-31',
                               'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum',
                               'models': 'era5', 'timezone': 'auto'})
    by_year = split_years(env['data'].get('daily') or {})
    rows = []
    for y in sorted(by_year):
        ix = year_indices(by_year[y])
        if ix['days'] >= 360 and ix['missing'] <= 10:  # año completo
            rows.append({'year': y, **ix})
    if not rows:
        raise ValueError('La serie ERA5 no trajo años completos')
    mean = {k: round(sum(r[k] for r in rows if r[k] is not None) / max(1, sum(1 for r in rows if r[k] is not None)), 1)
            for k in NUMERIC}
    last = rows[-1]
    anomaly = {k: (round(last[k] - mean[k], 1) if last[k] is not None else None) for k in NUMERIC}
    catalog = [{'key': k, 'xclim': x, 'label': l, 'unit': u, 'description': d} for k, x, l, u, d in INDICES]
    return c.envelope({'capability': 'ANALYSIS', 'period': [rows[0]['year'], last['year']],
                       'catalog': catalog, 'years': rows, 'mean': mean, 'last_year': last['year'],
                       'anomaly_last_year': anomaly,
                       'method': 'Definiciones xclim/ETCCDI calculadas sobre ERA5 diario en el punto del lote (grilla ~25 km).'},
                      ARCHIVE, f'índices agroclimáticos {years} años', 'ERA5 / Open-Meteo · índices xclim',
                      )


# ───────────────────────────── NOAA PSL ─────────────────────────────
PSL = {
    'nino34': ('Niño 3.4 (anomalía SST)', 'https://psl.noaa.gov/data/correlation/nina34.anom.data', '°C', 'enso'),
    'oni': ('ONI', 'https://psl.noaa.gov/data/correlation/oni.data', '°C', 'enso'),
    'meiv2': ('MEI v2', 'https://psl.noaa.gov/enso/mei/data/meiv2.data', 'índice', 'enso'),
    'nino12': ('Niño 1+2 (costa de Perú)', 'https://psl.noaa.gov/data/correlation/nina1.anom.data', '°C', 'enso'),
    'soi': ('SOI (Oscilación del Sur)', 'https://psl.noaa.gov/data/correlation/soi.data', 'índice', 'soi'),
    'aao': ('AAO / Modo Anular del Sur', 'https://psl.noaa.gov/data/correlation/aao.data', 'índice', 'other'),
    'tsa': ('Atlántico Sur tropical (TSA)', 'https://psl.noaa.gov/data/correlation/tsa.data', '°C', 'other'),
    'pdo': ('PDO (Pacífico decenal)', 'https://psl.noaa.gov/data/correlation/pdo.data', 'índice', 'other'),
}
MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def parse_psl(text):
    """Devuelve [(año, mes, valor)] sin faltantes."""
    lines = [l.split() for l in text.strip().splitlines() if l.strip()]
    if not lines or len(lines[0]) < 2:
        raise ValueError('Formato PSL inválido')
    y0, y1 = int(float(lines[0][0])), int(float(lines[0][1]))
    rows, missing = [], None
    for parts in lines[1:]:
        if len(parts) == 13 and parts[0].lstrip('-').isdigit() and y0 <= int(parts[0]) <= y1:
            rows.append((int(parts[0]), [float(v) for v in parts[1:]]))
        elif len(parts) >= 1 and missing is None and rows:
            try:
                missing = float(parts[0])
            except ValueError:
                pass
            break
    out = []
    for y, vals in rows:
        for m, v in enumerate(vals, 1):
            if missing is not None and abs(v - missing) < 1e-6:
                continue
            if v <= -99 or v >= 999:  # marcadores habituales -99.99 / 999
                continue
            out.append((y, m, v))
    if not out:
        raise ValueError('Serie PSL vacía')
    return out


def phase(key, v):
    kind = PSL[key][3]
    if kind == 'enso':
        return 'Niño' if v >= 0.5 else 'Niña' if v <= -0.5 else 'Neutro'
    if kind == 'soi':  # SOI negativo sostenido acompaña a El Niño
        return 'tipo Niño' if v <= -0.7 else 'tipo Niña' if v >= 0.7 else 'Neutro'
    return 'positivo' if v > 0 else 'negativo' if v < 0 else 'neutro'


def psl_index(key):
    name, url, unit, _ = PSL[key]
    series = parse_psl(c._get(url, timeout=20).text)
    y, m, v = series[-1]
    last12 = [{'period': f'{yy}-{mm:02d}', 'value': round(vv, 2)} for yy, mm, vv in series[-12:]]
    return c.envelope({'index': key, 'name': name, 'unit': unit, 'value': round(v, 2),
                       'period': f'{MONTHS[m - 1]} {y}', 'phase': phase(key, v), 'last12': last12},
                      url, f'{name} · mensual', 'NOAA PSL')


def psl_indices():
    out = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {k: pool.submit(psl_index, k) for k in PSL}
        for k, f in futs.items():
            try:
                out[k] = f.result()
            except Exception as e:
                out[k] = c.envelope({}, PSL[k][1], PSL[k][0], 'NOAA PSL', 'sin dato', type(e).__name__)
    ok = [k for k, v in out.items() if v['status'] == 'recibido']
    enso = [out[k]['data']['phase'] for k in ('nino34', 'oni', 'meiv2') if out[k]['status'] == 'recibido']
    consensus = max(set(enso), key=enso.count) if enso else None
    return c.envelope({'indices': out, 'enso_consensus': consensus,
                       'enso_agreement': f'{enso.count(consensus)}/{len(enso)}' if enso else None},
                      'https://psl.noaa.gov/data/climateindices/list/',
                      'teleconexiones mensuales (ENSO, SOI, AAO, TSA, PDO)', 'NOAA PSL',
                      'recibido' if ok else 'sin dato', None if ok else 'NOAA PSL no respondió')
