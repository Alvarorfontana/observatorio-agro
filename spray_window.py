"""spray_window v1.0 — ventana de pulverización por hora (idea de Solinftec / buenas prácticas de aspersión).

Para cada hora del pronóstico calcula si conviene pulverizar y por qué. Cinco factores, cada uno con su
umbral explícito y su escala (mínimo, máximo y bandas):
  viento      < 3 km/h inversión y deriva; 3-11 km/h óptimo; > 16 km/h no se pulveriza
  Delta T     temperatura menos bulbo húmedo (fórmula de Stull, 2011): 2-8 °C óptimo; < 2 condensación; > 10
              evaporación y no se deposita
  lluvia      lavado: no pulverizar si llueve ahora o en las próximas 4 h
  temperatura < 5 °C o > 30 °C reduce la deposición y daña el cultivo
  humedad     < 40 % seca la gota; > 95 % favorece lavado y enfermedades

El índice de aptitud es el MÍNIMO de los cinco puntajes: manda el factor limitante, no el promedio.
Devuelve por hora la fila completa con su escala y la mejor ventana contigua del día.
"""
import math

import scales

WIND_OPT = (3.0, 11.0)
DELTA_T_OPT = (2.0, 8.0)
RAIN_LOOKAHEAD = 4
DAY_START, DAY_END = 6, 20


def wet_bulb(temp_c, rh):
    """Temperatura de bulbo húmedo por la aproximación de Stull (2011)."""
    if temp_c is None or rh is None:
        return None
    t, r = float(temp_c), min(max(float(rh), 1.0), 100.0)
    return (t * math.atan(0.151977 * (r + 8.313659) ** 0.5) + math.atan(t + r) - math.atan(r - 1.676331)
            + 0.00391838 * r ** 1.5 * math.atan(0.023101 * r) - 4.686035)


def delta_t(temp_c, rh):
    wb = wet_bulb(temp_c, rh)
    return None if wb is None else round(float(temp_c) - wb, 2)


def _ramp(v, lo, hi):
    """0 fuera del rango, 100 dentro, con transición lineal en los bordes."""
    if v is None:
        return 0
    if lo <= v <= hi:
        return 100.0
    if v < lo:
        return max(0.0, 100.0 * v / lo) if lo else 0.0
    return max(0.0, 100.0 - (v - hi) * 8.0)


def scores(temp, rh, wind, rain4, dt):
    wind_s = 100.0 if WIND_OPT[0] <= (wind or 0) <= WIND_OPT[1] else _ramp(wind, *WIND_OPT)
    dt_s = 100.0 if DELTA_T_OPT[0] <= (dt or 0) <= DELTA_T_OPT[1] else _ramp(dt, *DELTA_T_OPT)
    rain_s = 0.0 if (rain4 or 0) > 0.1 else 100.0
    temp_s = _ramp(temp, 5.0, 30.0)
    rh_s = _ramp(rh, 40.0, 95.0)
    return {'wind': round(wind_s), 'delta_t': round(dt_s), 'rain': round(rain_s), 'temp': round(temp_s), 'humidity': round(rh_s)}


def evaluate(hourly, days=3):
    """hourly: dict de Open-Meteo (time, temperature_2m, relative_humidity_2m, wind_speed_10m, precipitation)."""
    t = (hourly or {}).get('time') or []
    temp = (hourly or {}).get('temperature_2m') or []
    rh = (hourly or {}).get('relative_humidity_2m') or []
    wind = (hourly or {}).get('wind_speed_10m') or []
    rain = (hourly or {}).get('precipitation') or []
    if not t or not temp:
        raise ValueError('Sin pronóstico horario para armar la ventana de pulverización')
    arrays = [temp, rh, wind, rain]
    n = min([len(t)] + [len(a) for a in arrays if a] + [days * 24])

    def at(arr, i):
        return arr[i] if i < len(arr) else None

    def rain_next(i):
        return sum(v or 0 for v in rain[i:i + RAIN_LOOKAHEAD + 1]) if rain else 0.0

    rows = []
    for i in range(n):
        rhi = at(rh, i)
        wnd = at(wind, i)
        dt = delta_t(temp[i], rhi)
        sc = scores(temp[i], rhi, wnd, rain_next(i), dt)
        idx = min(sc.values())
        rows.append({'time': t[i], 'temp_c': _r(temp[i], 1), 'rh_pct': _r(rhi, 0),
                     'wind_kph': _r(wnd, 1), 'delta_t_c': dt,
                     'rain_mm': _r(at(rain, i), 1), 'scores': sc, 'index': idx,
                     'wind_band': _band('wind_kph', wnd),
                     'delta_t_band': _band('delta_t', dt),
                     'index_band': _band('spray_index', idx)})
    return {'rows': rows, 'best': best_run(rows), 'hours': len(rows),
            'scales': {k: scales.describe(k) for k in ('wind_kph', 'delta_t', 'spray_index')},
            'thresholds': {'viento_kmh': list(WIND_OPT), 'delta_t_c': list(DELTA_T_OPT),
                           'lluvia_lavado_h': RAIN_LOOKAHEAD, 'franja_diurna_h': [DAY_START, DAY_END]},
            'reading': reading(rows)}


def _r(v, d):
    return None if v is None else round(float(v), d)


def _band(scale_id, v):
    b = scales.band(scale_id, v)
    return None if b is None else {'label': b['label'], 'tone': b['tone']}


def best_run(rows):
    """Primer tramo contiguo en horas diurnas con aptitud apta (≥ 70)."""
    run, best = [], None
    for r in rows:
        h = int(str(r['time'])[11:13]) if len(str(r['time'])) >= 13 else 0
        if r['index'] >= 70 and DAY_START <= h < DAY_END:
            run.append(r)
            if best is None or len(run) > len(best):
                best = list(run)
        else:
            run = []
    if not best:
        return None
    return {'date': str(best[0]['time'])[:10], 'from': str(best[0]['time'])[11:16], 'to': str(best[-1]['time'])[11:16],
            'hours': len(best), 'index': round(sum(x['index'] for x in best) / len(best))}


def reading(rows):
    if not rows:
        return 'Sin ventana evaluada.'
    apt = [r for r in rows if r['index'] >= 70]
    best = best_run(rows)
    if best:
        return (f"Mejor ventana en {best['hours']} hora(s) el {best['date']} de {best['from']} a {best['to']} "
                f"(aptitud {best['index']}/100). "
                f"{len(apt)} de {len(rows)} horas del pronóstico superan 70/100.")
    worst = min(rows, key=lambda r: r['index'])
    why = min(worst['scores'], key=worst['scores'].get)
    return (f"Sin ventana apta en el pronóstico: el factor limitante es {why} "
            f"(aptitud máxima {max(r['index'] for r in rows)}/100). No pulverizar.")


def advise(lat, lon, days=3):
    """Trae el horario de Open-Meteo y devuelve la ventana de pulverización."""
    import research_connectors as c
    env = c.external('https://api.open-meteo.com/v1/forecast',
                     {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': max(days, 2),
                      'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation'})
    data = evaluate((env.get('data') or {}).get('hourly') or {}, days)
    data['point'] = {'lat': lat, 'lon': lon}
    return c.envelope(data, env.get('source_url'), 'ventana de pulverización por hora',
                      'Open-Meteo · umbrales de aspersión', 'recibido' if data['rows'] else 'sin dato',
                      None if data['rows'] else 'Sin pronóstico horario')
