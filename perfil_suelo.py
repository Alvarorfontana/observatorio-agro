"""perfil_suelo v1.0 — agua en el perfil del suelo hasta 2,55 m y estado de la vegetación contra su propia historia.

Agua en el perfil: humedad volumétrica diaria de ERA5-Land (Copernicus, ~9 km) en cuatro capas: 0-7, 7-28, 28-100 y
100-255 cm. Se pasa a milímetros de agua (humedad × espesor de la capa) y se compara el último día con los mismos
días del año (±10 días) de 1991-2020: percentil y diferencia con la mediana. Es un modelo de superficie terrestre
alimentado por el reanálisis, no una medición en el lote: no conoce la napa ni el manejo, y el suelo es el de su
grilla. Sirve para saber si el perfil está más seco o más húmedo que lo normal para la fecha, capa por capa.
Referencia oficial argentina: balance hídrico del INTA (Clima y Agua) y reservas de la Oficina de Riesgo Agropecuario.

Estado de la vegetación: NDVI MODIS (250 m, cada 16 días) del lote desde 2001, vía Earth Engine. Cada compuesto se
compara con los compuestos de la misma época (±8 días) de los años anteriores: percentil y diferencia con la mediana.
También se calcula el índice de condición de la vegetación (VCI, Kogan): dónde cae el NDVI actual entre el mínimo y
el máximo de esa época en la serie (0 a 100; menos de 40 indica sequía), y cuántos días seguidos lleva el lote debajo
de lo normal (persistencia, hasta 112 días). Son los mismos indicadores que publica SEPA (INTA) en mapas nacionales,
calculados acá para el perímetro del lote.
"""
from datetime import date, timedelta
from statistics import median

import research_connectors as c

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
LAYERS = [('soil_moisture_0_to_7cm_mean', '0-7 cm', 70), ('soil_moisture_7_to_28cm_mean', '7-28 cm', 210),
          ('soil_moisture_28_to_100cm_mean', '28-100 cm', 720), ('soil_moisture_100_to_255cm_mean', '100-255 cm', 1550)]
OFFICIAL = [{'name': 'INTA · balance hídrico hasta 2 m (Instituto de Clima y Agua)', 'url': 'https://inta.gob.ar'},
            {'name': 'Oficina de Riesgo Agropecuario · reservas de agua en el suelo (datos abiertos)',
             'url': 'https://datos.gob.ar/dataset/agroindustria-ora---reservas-agua-suelo'}]


def pclass(p):
    if p is None: return 'sin dato'
    if p < 10: return 'muy seco'
    if p < 25: return 'seco'
    if p <= 75: return 'normal'
    if p <= 90: return 'húmedo'
    return 'muy húmedo'


def percentile(v, ref, min_n=30):
    ref = [r for r in ref if r is not None]
    if v is None or len(ref) < min_n:
        return None
    below = sum(1 for r in ref if r < v) + 0.5 * sum(1 for r in ref if r == v)
    return round(100 * below / len(ref))


def _doy_close(a, b, w):
    d = abs(a.timetuple().tm_yday - b.timetuple().tm_yday)
    return min(d, 365 - d) <= w


def analyze_profile(daily):
    t = [date.fromisoformat(x) for x in daily.get('time') or []]
    cols = {k: daily.get(k) or [None] * len(t) for k, *_ in LAYERS}
    mm = []
    for i in range(len(t)):
        vals = [cols[k][i] for k, *_ in LAYERS]
        mm.append(None if any(v is None for v in vals) else [v * th for v, (_, _, th) in zip(vals, LAYERS)])
    last = next((i for i in range(len(t) - 1, -1, -1) if mm[i] is not None), None)
    if last is None:
        raise ValueError('ERA5-Land no trajo humedad del suelo para el punto')
    day = t[last]
    ref_idx = [i for i in range(len(t)) if 1991 <= t[i].year <= 2020 and mm[i] is not None and _doy_close(t[i], day, 10)]
    layers = []
    for j, (k, label, th) in enumerate(LAYERS):
        ref = [mm[i][j] for i in ref_idx]
        v = mm[last][j]
        p = percentile(v, ref)
        layers.append({'layer': label, 'mm': round(v), 'normal_mm': round(median(ref)) if ref else None,
                       'diff_mm': round(v - median(ref)) if ref else None, 'percentile': p, 'class': pclass(p)})

    def tot(i, upto):
        return sum(mm[i][:upto])
    out = {'date': day.isoformat(), 'layers': layers}
    for key, upto, label in (('to_1m', 3, 'hasta 1 m'), ('to_2_5m', 4, 'hasta 2,55 m')):
        ref = [tot(i, upto) for i in ref_idx]
        v = tot(last, upto); p = percentile(v, ref)
        out[key] = {'label': label, 'mm': round(v), 'normal_mm': round(median(ref)) if ref else None,
                    'diff_mm': round(v - median(ref)) if ref else None, 'percentile': p, 'class': pclass(p)}
    recent = []
    for i in range(max(0, last - 89), last + 1):
        if mm[i] is None:
            continue
        ref = [tot(r, 4) for r in range(len(t)) if 1991 <= t[r].year <= 2020 and mm[r] is not None and _doy_close(t[r], t[i], 3)]
        recent.append({'date': t[i].isoformat(), 'mm': round(tot(i, 4)), 'normal_mm': round(median(ref)) if ref else None})
    out['recent_90d'] = recent
    a, b = out['to_1m'], out['to_2_5m']
    out['reading'] = (f"Al {day.strftime('%d/%m')} el perfil hasta 1 m está {a['class']} (percentil {a['percentile']}, "
                      f"{'+' if (a['diff_mm'] or 0) > 0 else ''}{a['diff_mm']} mm contra lo normal) y hasta 2,55 m está {b['class']} "
                      f"(percentil {b['percentile']}).")
    return out


def soil_profile(lat, lon):
    end = c._now().date() - timedelta(days=6)
    env = c.external(ARCHIVE, {'latitude': lat, 'longitude': lon, 'start_date': '1991-01-01', 'end_date': end.isoformat(),
                               'daily': ','.join(k for k, *_ in LAYERS), 'models': 'era5_land', 'timezone': 'UTC'},
                     scope='agua en el perfil del suelo (ERA5-Land)', organism='Copernicus ERA5-Land vía Open-Meteo')
    data = analyze_profile((env['data'] or {}).get('daily') or {})
    data.update(method=__doc__.split('\n\n')[1].strip(), official=OFFICIAL)
    return c.envelope(data, ARCHIVE, 'agua en el perfil del suelo hasta 2,55 m', 'Copernicus ERA5-Land vía Open-Meteo')


def vci_class(v):
    """Índice de condición de la vegetación (Kogan): 0 = el peor de la serie para la época, 100 = el mejor."""
    if v is None: return 'sin dato'
    if v < 10: return 'sequía extrema'
    if v < 20: return 'sequía severa'
    if v < 30: return 'sequía moderada'
    if v < 40: return 'sequía leve'
    return 'sin sequía'


def analyze_ndvi(rows):
    pts = [(date.fromisoformat(r['datetime'][:10]), r['ndvi_mean']) for r in rows if r.get('ndvi_mean') is not None]
    pts.sort()
    if len(pts) < 46:
        raise ValueError('Serie NDVI demasiado corta para comparar con otros años')
    out = []
    for d, v in pts[-12:]:
        ref = [x for dd, x in pts if dd.year < d.year and _doy_close(dd, d, 8)]
        p = percentile(v, ref, min_n=5)
        vci = round(100 * (v - min(ref)) / (max(ref) - min(ref))) if len(ref) >= 5 and max(ref) > min(ref) else None
        if vci is not None:
            vci = max(0, min(100, vci))
        out.append({'date': d.isoformat(), 'ndvi': round(v, 3), 'normal': round(median(ref), 3) if ref else None,
                    'diff': round(v - median(ref), 3) if ref else None, 'percentile': p, 'years': len(ref),
                    'vci': vci, 'vci_class': vci_class(vci)})
    last = out[-1]
    # persistencia (como el indicador temporal de SEPA-INTA): compuestos seguidos, hasta el último, debajo de la mediana
    run = 0
    for r in reversed(out):
        if r['diff'] is not None and r['diff'] < 0:
            run += 1
        else:
            break
    persistence = {'composites': run, 'days': run * 16, 'max_days': 112}
    p = 50 if last['percentile'] is None else last['percentile']
    word = ('muy por debajo' if p < 10 else 'por debajo' if p < 25 else 'muy por encima' if p > 90 else 'por encima' if p > 75 else 'dentro')
    if last['normal'] is None:
        raise ValueError('No hay años anteriores con la misma época para comparar')
    reading = (f"El último compuesto ({date.fromisoformat(last['date']).strftime('%d/%m/%Y')}) tiene NDVI {last['ndvi']:.2f}, "
               f"{word} de lo normal para la época (mediana {last['normal']:.2f} en {last['years']} años; percentil {last['percentile']}).")
    if last.get('vci') is not None:
        reading += f" Índice de condición de la vegetación (VCI): {last['vci']} ({last['vci_class']})."
    if run >= 2:
        reading += f" Lleva {min(run * 16, 112) if run * 16 <= 112 else 'más de 112'} días seguidos por debajo de lo normal."
    return {'series': out, 'latest': last, 'reading': reading, 'persistence': persistence}


def ndvi_anomaly(polygon):
    import vegetation as veg
    env = veg.gee_ndvi(polygon, 25)
    if env.get('status') != 'recibido':
        return env
    d = env['data']
    data = analyze_ndvi(d.get('series') or [])
    data.update(sensor=d.get('sensor'), area_ha=d.get('area_ha'), method=__doc__.split('\n\n')[2].strip())
    return c.envelope(data, env.get('source_url'), 'NDVI del lote contra su propia historia', 'NASA MODIS vía Google Earth Engine')
