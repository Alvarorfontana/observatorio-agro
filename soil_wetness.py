"""soil_wetness — humedad del suelo de NASA (MERRA-2 vía NASA POWER) comparada con lo normal.

Es una segunda opinión independiente de la humedad de Open-Meteo: otro modelo, otra agencia.
  - GWETTOP: capa superficial (0-5 cm); GWETROOT: zona de raíces (0-100 cm); GWETPROF: perfil completo.
  - Valores 0 a 1 (fracción de saturación) → se informan en %.
  - "Lo normal" sale de los mismos meses de los últimos 20 años en el mismo punto: percentil y categoría.
Abierto, sin clave. Si NASA no responde, se informa sin dato; no se inventa nada.
"""
from datetime import timedelta

import research_connectors as c

DAILY = 'https://power.larc.nasa.gov/api/temporal/daily/point'
MONTHLY = 'https://power.larc.nasa.gov/api/temporal/monthly/point'
PARAMS = 'GWETTOP,GWETROOT,GWETPROF'
FILL = -999
YEARS = 20


def _clean(series):
    """{'20260901': 0.41, ...} → [(fecha ISO, valor)] sin faltantes, ordenado."""
    out = []
    for k, v in sorted((series or {}).items()):
        if v is None or v <= FILL + 1 or len(k) != 8:
            continue
        out.append((f'{k[:4]}-{k[4:6]}-{k[6:]}', float(v)))
    return out


def percentile_rank(value, history):
    hs = [h for h in history if h is not None]
    if value is None or len(hs) < 5:
        return None
    below = sum(1 for h in hs if h < value); equal = sum(1 for h in hs if h == value)
    return round(100 * (below + 0.5 * equal) / len(hs))


def category(pct):
    if pct is None:
        return None
    if pct < 10: return 'muy seco'
    if pct < 30: return 'más seco que lo normal'
    if pct <= 70: return 'normal'
    if pct <= 90: return 'más húmedo que lo normal'
    return 'muy húmedo'


def monthly_history(monthly, month):
    """Valores del mismo mes en cada año ({'YYYYMM': v}, ignora 'YYYY13' anual)."""
    return [float(v) for k, v in (monthly or {}).items()
            if len(k) == 6 and k[4:] == f'{month:02d}' and v is not None and v > FILL + 1]


def summarize(daily_param, monthly_root):
    root = _clean(daily_param.get('GWETROOT'))
    top = _clean(daily_param.get('GWETTOP'))
    prof = _clean(daily_param.get('GWETPROF'))
    if not root:
        raise ValueError('NASA POWER no trajo humedad de suelo para este punto')
    last_date, last_root = root[-1]
    month = int(last_date[5:7])
    tail = [v for d, v in root if d[5:7] == last_date[5:7] and d[:4] == last_date[:4]]
    month_mean = sum(tail) / len(tail)
    hist = monthly_history(monthly_root, month)
    pct = percentile_rank(month_mean, hist)
    normal = sum(hist) / len(hist) if hist else None
    ago = [v for d, v in root if d <= _shift(last_date, -30)]
    change = (last_root - ago[-1]) if ago else None
    pc = lambda v: None if v is None else round(100 * v, 1)
    return {
        'date': last_date,
        'top_pct': pc(top[-1][1]) if top else None,
        'root_pct': pc(last_root),
        'profile_pct': pc(prof[-1][1]) if prof else None,
        'month_mean_pct': pc(month_mean),
        'normal_pct': pc(normal),
        'anomaly_pts': None if normal is None else round(100 * (month_mean - normal), 1),
        'percentile': pct,
        'category': category(pct),
        'change_30d_pts': None if change is None else round(100 * change, 1),
        'years': len(hist),
        'series': [{'date': d, 'root_pct': pc(v)} for d, v in root[-75:]],
        'normal_range': _band(hist),
    }


def _band(hist):
    if len(hist) < 5:
        return None
    s = sorted(hist)
    q = lambda p: s[min(len(s) - 1, max(0, round(p * (len(s) - 1))))]
    return {'p10': round(100 * q(.1), 1), 'p90': round(100 * q(.9), 1)}


def _shift(iso, days):
    from datetime import date
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def analyze(lat, lon):
    end = c._now().date() - timedelta(days=2)
    start = end - timedelta(days=90)
    daily = c.external(DAILY, {'parameters': PARAMS, 'community': 'AG', 'latitude': lat, 'longitude': lon,
                               'start': start.strftime('%Y%m%d'), 'end': end.strftime('%Y%m%d'), 'format': 'JSON'},
                       scope='humedad de suelo diaria', organism='NASA POWER (MERRA-2)')
    y1 = c._now().year - 1
    monthly = c.external(MONTHLY, {'parameters': 'GWETROOT', 'community': 'AG', 'latitude': lat, 'longitude': lon,
                                   'start': y1 - YEARS + 1, 'end': y1, 'format': 'JSON'},
                         scope=f'humedad de suelo mensual {YEARS} años', organism='NASA POWER (MERRA-2)')
    dp = ((daily['data'] or {}).get('properties') or {}).get('parameter') or {}
    mp = (((monthly['data'] or {}).get('properties') or {}).get('parameter') or {}).get('GWETROOT') or {}
    data = summarize(dp, mp)
    return c.envelope(data, DAILY, 'humedad de suelo vs lo normal', 'NASA POWER (MERRA-2)')
