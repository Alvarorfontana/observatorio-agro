"""enso_panel v1.0 — El Niño para toda la región: estado oficial, índices, historia y rangos.

Fuentes (NOAA CPC, dominio público, sin clave):
  * ONI  https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt   (SEAS YR TOTAL ANOM)
  * RONI https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt  (SEAS YR ANOM) — índice relativo,
    descuenta el calentamiento de todo el trópico; NOAA lo usa desde 2026 para declarar fases.
  * Niño 3.4 semanal https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for (base 1991-2020)
  * Estado del sistema de alerta: discusión diagnóstica mensual de CPC.

Categorías de intensidad (convención usada por IRI y NOAA para la anomalía trimestral):
  ±0,5 a 0,9 débil · 1,0 a 1,4 moderado · 1,5 a 1,9 fuerte · 2,0 o más muy fuerte.
"""
import re
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c

ONI_URL = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
RONI_URL = 'https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt'
WEEKLY_URL = 'https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for'
DISC_URL = 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml'

SEASONS = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']
SEAS_ES = ['DEF', 'EFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDE']
RANGES = [(2.0, 'muy fuerte'), (1.5, 'fuerte'), (1.0, 'moderado'), (0.5, 'débil')]
STATUS_ES = {'El Niño Advisory': 'Advertencia de El Niño', 'El Niño Watch': 'Vigilancia de El Niño',
             'La Niña Advisory': 'Advertencia de La Niña', 'La Niña Watch': 'Vigilancia de La Niña',
             'Final El Niño Advisory': 'Fin de El Niño', 'Final La Niña Advisory': 'Fin de La Niña',
             'Not Active': 'Sin alerta'}

# Lo ocurrido en la región en los Niños más fuertes desde 1950 (registro histórico, no pronóstico).
REGION_EVENTS = {
    1982: 'Gran creciente del Paraná y del Uruguay en 1983, de las mayores del siglo.',
    1997: 'Inundaciones extensas en el Litoral entre 1997 y 1998; crecida grande del Paraná.',
    2015: 'Crecidas del Uruguay y del Paraná entre diciembre de 2015 y 2016, con evacuados en Concordia y el NEA.',
    2023: 'Lluvias excesivas en el sur de Brasil; inundación histórica de Rio Grande do Sul en mayo de 2024.',
}


def category(v):
    """Fase e intensidad para una anomalía trimestral."""
    if v is None:
        return {'phase': None, 'strength': None}
    a = abs(v)
    phase = 'El Niño' if v >= 0.5 else 'La Niña' if v <= -0.5 else 'Neutro'
    strength = next((n for t, n in RANGES if a >= t), None) if phase != 'Neutro' else None
    return {'phase': phase, 'strength': strength}


def parse_seasonal(text):
    """oni.ascii.txt y RONI.ascii.txt: SEAS YR [TOTAL] ANOM. La anomalía es siempre la última columna."""
    out = []
    for line in text.strip().splitlines():
        p = line.split()
        if len(p) < 3 or p[0] not in SEASONS:
            continue
        try:
            out.append({'season': p[0], 'season_es': SEAS_ES[SEASONS.index(p[0])], 'year': int(p[1]), 'anom': float(p[-1])})
        except ValueError:
            continue
    return out


def parse_weekly(text):
    """wksst9120.for: '07OCT2026     20.9 0.4     25.9 1.6     28.6 2.1     29.6 1.0' (SST y anomalía pegados a veces)."""
    out = []
    for line in text.splitlines():
        m = re.match(r'\s*(\d{2}[A-Z]{3}\d{4})\s+(.*)', line)
        if not m:
            continue
        nums = re.findall(r'-?\d+\.\d', m.group(2))
        if len(nums) < 8:
            continue
        out.append({'week': m.group(1), 'nino12': float(nums[1]), 'nino3': float(nums[3]), 'nino34': float(nums[5]), 'nino4': float(nums[7])})
    return out


def parse_status(html):
    """Busca la frase de estado después de 'ENSO Alert System Status:' sin depender del marcado HTML."""
    import html as _h
    text = re.sub(r'\s+', ' ', _h.unescape(re.sub(r'<[^>]+>', ' ', html or '')))
    i = text.find('ENSO Alert System Status:')
    if i < 0:
        return None
    tail = text[i + 25:i + 80]
    for en in sorted(STATUS_ES, key=len, reverse=True):
        if tail.strip().startswith(en):
            return {'en': en, 'es': STATUS_ES[en]}
    return None


def episodes(series, threshold=0.5, min_len=5):
    """Episodios Niño: al menos 5 trimestres seguidos con anomalía ≥ 0,5 (definición operativa de NOAA)."""
    eps, run = [], []
    for r in series + [{'anom': -9}]:
        if r['anom'] >= threshold:
            run.append(r)
        else:
            if len(run) >= min_len or (run and run[-1] is series[-1]):   # el episodio en curso se muestra aunque aún no sume 5
                peak = max(run, key=lambda x: x['anom'])
                eps.append({'start': run[0]['year'], 'end': run[-1]['year'], 'from': f"{run[0]['season_es']} {run[0]['year']}",
                            'to': f"{run[-1]['season_es']} {run[-1]['year']}", 'peak': peak['anom'],
                            'peak_at': f"{peak['season_es']} {peak['year']}", 'strength': category(peak['anom'])['strength'],
                            'region': next((t for y, t in REGION_EVENTS.items() if run[0]['year'] <= y <= run[-1]['year']), None),
                            'ongoing': run[-1] is series[-1]})
            run = []
    return eps


def enso_panel():
    jobs = {'oni': ONI_URL, 'roni': RONI_URL, 'weekly': WEEKLY_URL, 'status': DISC_URL}
    raw, errors = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {k: pool.submit(c._get, u, None, None, 20) for k, u in jobs.items()}
        for k, f in futs.items():
            try:
                r = f.result()
                if r.ok:
                    raw[k] = r.text
                else:
                    errors[k] = f'HTTP {r.status_code}'
            except Exception as e:
                errors[k] = type(e).__name__
    oni = parse_seasonal(raw.get('oni', ''))
    roni = parse_seasonal(raw.get('roni', ''))
    weekly = parse_weekly(raw.get('weekly', ''))
    status = parse_status(raw.get('status'))
    last = lambda s: s[-1] if s else None
    lo, lr, lw = last(oni), last(roni), last(weekly)
    ref = lr or lo
    data = {
        'status': status,
        'oni': {**lo, **category(lo['anom'])} if lo else None,
        'roni': {**lr, **category(lr['anom'])} if lr else None,
        'weekly': {**lw, **category(lw['nino34'])} if lw else None,
        'phase': category(ref['anom']) if ref else None,
        'series': {'oni': oni[-72:], 'roni': roni[-72:], 'weekly': weekly[-52:]},
        'events': [e for e in episodes(oni) if e['peak'] >= 1.5][::-1],
        'ranges': [{'from': 2.0, 'label': 'Muy fuerte'}, {'from': 1.5, 'label': 'Fuerte'}, {'from': 1.0, 'label': 'Moderado'},
                   {'from': 0.5, 'label': 'Débil'}, {'from': -0.5, 'label': 'Neutro (entre −0,5 y +0,5)'}],
        'errors': errors,
    }
    ok = bool(oni or roni or weekly)
    return c.envelope(data, 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/',
                      'El Niño: estado oficial, ONI, RONI y Niño 3.4 semanal', 'NOAA CPC',
                      'recibido' if ok else 'sin dato', None if ok else 'NOAA CPC no respondió')
