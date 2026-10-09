"""rainfall v2.7 — lluvia observada CHIRPS por lote y sequía tipo SPI.

CHIRPS v2 (Climate Hazards Center, UCSB): lluvia diaria desde 1981, ~5 km, satélite + estaciones.
Acceso por la API pública ClimateSERV (NASA/USAID SERVIR), la misma que usa el paquete
rOpenSci `chirps` (https://github.com/ropensci/chirps):
  submitDataRequest → getDataRequestProgress → getDataFromRequest.
El trabajo es asíncrono: DOTS lo inicia, el navegador consulta el avance, y al terminar
se calculan lluvia mensual, normal 1991-2020, anomalías y un SPI empírico por percentiles.
"""
import json, math
from datetime import date, datetime

import research_connectors as c

API = 'https://climateserv.servirglobal.net/api'
DATATYPE_CHIRPS = 0      # CHIRPS diario
OP_AVERAGE = 5           # promedio espacial sobre el polígono
NORMAL = (1991, 2020)


def _mdy(d):
    return d.strftime('%m/%d/%Y')


def start(polygon, start_year=1991):
    import vegetation as veg  # reutiliza la validación y el GeoJSON del lote
    geom = veg.geojson_polygon(polygon)
    end = c._now().date()
    params = {'datatype': DATATYPE_CHIRPS, 'begintime': _mdy(date(int(start_year), 1, 1)), 'endtime': _mdy(end),
              'intervaltype': 0, 'operationtype': OP_AVERAGE, 'callback': 'successCallback',
              'dateType_Category': 'default', 'isZip_CurrentDataType': 'false', 'geometry': json.dumps(geom)}
    r = c._get(API + '/submitDataRequest/', params, timeout=30)
    txt = r.text.strip()
    job = txt.split('"')[1] if '"' in txt else txt
    if not job or len(job) > 80 or not all(ch.isalnum() or ch in '-_' for ch in job):
        raise ValueError('ClimateSERV no devolvió un trabajo válido')
    return c.envelope({'job': job, 'status': 'en proceso', 'start': start_year}, API + '/submitDataRequest/',
                      'lluvia CHIRPS diaria sobre el lote · trabajo iniciado', 'CHC / ClimateSERV')


def _check_job(job):
    if not isinstance(job, str) or not job or len(job) > 80 or not all(ch.isalnum() or ch in '-_' for ch in job):
        raise ValueError('Trabajo inválido')


def progress(job):
    _check_job(job)
    t = c._get(API + '/getDataRequestProgress/', {'id': job}, timeout=20).text.strip()
    try:
        v = float(t.strip('[]"() \n').split(',')[0])
    except ValueError:
        raise ValueError('Avance ilegible')
    if v < 0:
        raise ValueError('ClimateSERV informó un error en el trabajo')
    return v


def parse_series(payload):
    """Acepta {'data':[{'date':'MM/DD/YYYY','value':{'avg':x}}]} y variantes."""
    rows = (payload or {}).get('data') or []
    out = {}
    for r in rows:
        d = r.get('date'); v = r.get('value')
        if isinstance(v, dict):
            v = v.get('avg', v.get('mean'))
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v < 0 or not math.isfinite(v):  # -9999 = sin dato
            continue
        try:
            dt = datetime.strptime(d, '%m/%d/%Y').date()
        except (TypeError, ValueError):
            try:
                dt = date.fromisoformat(str(d)[:10])
            except ValueError:
                continue
        out[dt] = v
    return out


def _percentile_rank(values, x):
    vs = sorted(v for v in values if v is not None)
    if not vs:
        return None
    below = sum(1 for v in vs if v < x); equal = sum(1 for v in vs if v == x)
    return (below + 0.5 * equal) / len(vs)


def _spi_from_p(p):
    """SPI empírico: cuantil normal estándar del percentil (aprox. de Acklam / Beasley-Springer)."""
    if p is None:
        return None
    p = min(max(p, 0.01), 0.99)
    # aproximación racional de la inversa de la normal
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    cc = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((cc[0]*q+cc[1])*q+cc[2])*q+cc[3])*q+cc[4])*q+cc[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > 1 - 0.02425:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((cc[0]*q+cc[1])*q+cc[2])*q+cc[3])*q+cc[4])*q+cc[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def spi_class(s):
    if s is None:
        return 'sin dato'
    if s <= -2: return 'sequía extrema'
    if s <= -1.5: return 'sequía severa'
    if s <= -1: return 'sequía moderada'
    if s < 1: return 'normal'
    if s < 1.5: return 'húmedo'
    if s < 2: return 'muy húmedo'
    return 'extremadamente húmedo'


def analyze(daily, today=None):
    """daily: {date: mm}. Devuelve meses, normal, anomalías y SPI 1/3/6/12."""
    if not daily:
        raise ValueError('CHIRPS no devolvió valores para el lote')
    months = {}
    for d, v in daily.items():
        k = (d.year, d.month)
        m = months.setdefault(k, [0.0, 0])
        m[0] += v; m[1] += 1
    # sólo meses completos (CHIRPS publica con ~3 semanas de demora)
    import calendar
    full = {k: round(v[0], 1) for k, v in months.items() if v[1] >= calendar.monthrange(*k)[1] - 1}
    if not full:
        raise ValueError('No hay meses completos de CHIRPS')
    keys = sorted(full)
    last = keys[-1]

    def accum(ym, n):
        y, m = ym; tot = 0.0
        for i in range(n):
            mm = m - i; yy = y
            while mm <= 0:
                mm += 12; yy -= 1
            if (yy, mm) not in full:
                return None
            tot += full[(yy, mm)]
        return tot

    spi = {}
    for n in (1, 3, 6, 12):
        ref = [accum((y, last[1]), n) for y in range(NORMAL[0], NORMAL[1] + 1)]
        ref = [x for x in ref if x is not None]
        x = accum(last, n)
        if x is None or len(ref) < 20:
            spi[n] = {'mm': None, 'normal': None, 'spi': None, 'class': 'sin dato'}
            continue
        s = _spi_from_p(_percentile_rank(ref, x))
        spi[n] = {'mm': round(x, 1), 'normal': round(sorted(ref)[len(ref) // 2], 1),
                  'spi': round(s, 2), 'class': spi_class(s)}
    normal_month = {}
    for m in range(1, 13):
        vals = sorted(full[(y, m)] for y in range(NORMAL[0], NORMAL[1] + 1) if (y, m) in full)
        normal_month[m] = round(vals[len(vals) // 2], 1) if vals else None
    recent = keys[-12:]
    series = [{'period': f'{y}-{m:02d}', 'mm': full[(y, m)], 'normal': normal_month[m],
               'anomaly': round(full[(y, m)] - normal_month[m], 1) if normal_month[m] is not None else None}
              for y, m in recent]
    years = {}
    for (y, m), v in full.items():
        years.setdefault(y, []).append(v)
    annual = [{'year': y, 'mm': round(sum(v), 1)} for y, v in sorted(years.items()) if len(v) == 12]
    return {'capability': 'ANALYSIS', 'product': 'CHIRPS v2 diario (~5 km), promedio sobre el lote',
            'last_month': f'{last[0]}-{last[1]:02d}', 'normal_period': list(NORMAL),
            'spi': {str(k): v for k, v in spi.items()}, 'recent': series, 'annual': annual[-30:],
            'method': 'Lluvia mensual sumada de CHIRPS diario. Normal: mediana 1991-2020. SPI empírico: '
                      'percentil del acumulado frente a los mismos meses de 1991-2020, llevado a la escala normal estándar.'}


def result(job):
    p = progress(job)
    if p < 100:
        return c.envelope({'job': job, 'status': 'en proceso', 'progress': round(p)}, API + '/getDataRequestProgress/',
                          'lluvia CHIRPS · procesando', 'CHC / ClimateSERV')
    payload = c._get(API + '/getDataFromRequest/', {'id': job}, timeout=40).json()
    data = analyze(parse_series(payload))
    data['job'] = job; data['status'] = 'listo'
    return c.envelope(data, API + '/getDataFromRequest/', 'lluvia observada CHIRPS por lote y SPI', 'CHC / ClimateSERV')
