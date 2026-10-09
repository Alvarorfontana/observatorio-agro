"""alerts v2.9 — alertas del lote a partir de datos verificados.

Cada regla usa una fuente declarada y un umbral explícito. Si la fuente no respondió, la regla
queda como "sin evaluar" (nunca se emite una alerta ni un "todo bien" sin datos).

Reglas
  helada      conjunto ECMWF/GFS: prob. de mínima < 0 °C en los próximos 7 días ≥ 30 %
  calor       THI horario (Open-Meteo, 3 días) ≥ 79 alto / ≥ 84 severo; o prob. de máx ≥ 35 °C ≥ 40 %
  lluvia      prob. de ≥ 25 mm en un día ≥ 40 % o pronóstico diario ≥ 50 mm
  sequía      SPI 3 o 12 meses (CHIRPS) ≤ −1, o balance lluvia − ET₀ a 7 días < −25 mm
  fuego       NASA FIRMS: detección dentro del lote (alta) o en el entorno (media)
  vegetación  caída de NDVI medio ≥ 0,10 entre las dos últimas escenas válidas (Sentinel-2)
"""
from concurrent.futures import ThreadPoolExecutor
import os

import research_connectors as c

LEVELS = {'alta': 3, 'media': 2, 'baja': 1}


def thi(t, rh):
    return (1.8 * t + 32) - (0.55 - 0.0055 * rh) * (1.8 * t - 26)


def _alert(key, level, title, detail, source, action, when=None):
    return {'key': key, 'level': level, 'title': title, 'detail': detail, 'source': source, 'action': action, 'when': when}


def rule_frost(ens):
    days = (ens or {}).get('days') or []
    if not days:
        return None, 'sin pronóstico por conjunto'
    hits = [d for d in days[:7] if (d.get('p_frost') or 0) >= 30]
    if not hits:
        return [], None
    top = max(hits, key=lambda d: d['p_frost'])
    lvl = 'alta' if top['p_frost'] >= 60 else 'media'
    return [_alert('helada', lvl, 'Helada probable',
                   f"{top['p_frost']} % de los pronósticos dan mínima bajo 0 °C el {top['date'][8:10]}/{top['date'][5:7]} "
                   f"(mediana {top.get('tmin_med')} °C). {len(hits)} día(s) con riesgo en la semana.",
                   'Conjuntos ECMWF IFS y GFS', 'Prever reservas de forraje, proteger aguadas y revisar categorías sensibles.',
                   top['date'])], None


def rule_heat(hourly, ens):
    out = []
    t = (hourly or {}).get('temperature_2m') or []; rh = (hourly or {}).get('relative_humidity_2m') or []
    times = (hourly or {}).get('time') or []
    vals = [(times[i], thi(t[i], rh[i])) for i in range(min(len(t), len(rh), 72)) if t[i] is not None and rh[i] is not None]
    if vals:
        when, mx = max(vals, key=lambda x: x[1])
        hours = sum(1 for _, v in vals if v >= 79)
        if mx >= 79:
            out.append(_alert('calor', 'alta' if mx >= 84 else 'media', 'Estrés por calor en el rodeo',
                              f'THI máximo {mx:.0f} el {when[8:10]}/{when[5:7]} a las {when[11:16]}; {hours} horas en nivel alto o más en 3 días.',
                              'Open-Meteo · temperatura y humedad horarias', 'Asegurar sombra y agua, evitar arreos y manejo en horas de calor.', when))
    days = (ens or {}).get('days') or []
    hot = [d for d in days[:7] if (d.get('p_heat35') or 0) >= 40]
    if hot and not out:
        d = max(hot, key=lambda x: x['p_heat35'])
        out.append(_alert('calor', 'media', 'Calor extremo probable',
                          f"{d['p_heat35']} % de chance de máxima de 35 °C o más el {d['date'][8:10]}/{d['date'][5:7]}.",
                          'Conjuntos ECMWF IFS y GFS', 'Planificar sombra, agua y horarios de manejo.', d['date']))
    if not vals and not days:
        return None, 'sin pronóstico horario ni conjunto'
    return out, None


def rule_rain(ens, daily):
    out = []
    days = (ens or {}).get('days') or []
    wet = [d for d in days[:7] if (d.get('p_rain25') or 0) >= 40]
    pr = (daily or {}).get('precipitation_sum') or []; dt = (daily or {}).get('time') or []
    big = [(dt[i], pr[i]) for i in range(min(len(pr), len(dt))) if pr[i] is not None and pr[i] >= 50]
    if wet or big:
        if big:
            d, v = max(big, key=lambda x: x[1])
            det = f'Pronóstico de {v:.0f} mm el {d[8:10]}/{d[5:7]}.'
        else:
            d = max(wet, key=lambda x: x['p_rain25'])['date']
            det = f"{max(x['p_rain25'] for x in wet)} % de chance de 25 mm o más en un día ({d[8:10]}/{d[5:7]})."
        out.append(_alert('lluvia', 'alta' if big else 'media', 'Lluvia intensa · riesgo de anegamiento', det,
                          'Open-Meteo · pronóstico y conjuntos', 'Mover hacienda de bajos, revisar alambrados y accesos.', d))
    if not days and not pr:
        return None, 'sin pronóstico de lluvia'
    return out, None


def rule_drought(lluvia, daily):
    out = []
    spi = (lluvia or {}).get('spi') or {}
    worst = None
    for k in ('3', '12'):
        x = spi.get(k) or {}
        if x.get('spi') is not None and x['spi'] <= -1 and (worst is None or x['spi'] < worst[1]['spi']):
            worst = (k, x)
    if worst:
        k, x = worst
        out.append(_alert('sequia', 'alta' if x['spi'] <= -1.5 else 'media', f'Sequía · {x["class"]}',
                          f"Lluvia de los últimos {k} meses: {x['mm']:.0f} mm frente a {x['normal']:.0f} mm normales (SPI {x['spi']:.1f}).",
                          'CHIRPS · Climate Hazards Center', 'Ajustar carga y reservas; priorizar aguadas seguras.'))
    pr = (daily or {}).get('precipitation_sum') or []; et = (daily or {}).get('et0_fao_evapotranspiration') or []
    if pr and et:
        bal = sum(v or 0 for v in pr[:7]) - sum(v or 0 for v in et[:7])
        if bal < -25 and not worst:
            out.append(_alert('sequia', 'baja', 'Déficit hídrico en la semana',
                              f'La atmósfera pedirá {abs(bal):.0f} mm más de lo que se espera que llueva en 7 días.',
                              'Open-Meteo · lluvia y ET₀', 'Seguir humedad del suelo y estado de las aguadas.'))
    if not spi and not pr:
        return None, 'sin lluvia observada ni balance'
    return out, None


def rule_fire(firms):
    if firms is None:
        return None, 'FIRMS sin consultar o sin clave'
    det = (firms or {}).get('detections') or []
    inside = [d for d in det if d.get('inside_lot') is True]
    if inside:
        d = inside[0]
        return [_alert('fuego', 'alta', 'Foco de calor dentro del lote',
                       f"{len(inside)} detección(es) VIIRS; la última {d.get('acq_date')} {d.get('acq_time')} (confianza {d.get('confidence')}).",
                       'NASA FIRMS · VIIRS', 'Verificar en el campo de inmediato y avisar a bomberos si corresponde.', d.get('acq_date'))], None
    if det:
        return [_alert('fuego', 'media', 'Focos de calor en el entorno', f'{len(det)} detección(es) en los últimos 3 días cerca del lote.',
                       'NASA FIRMS · VIIRS', 'Revisar dirección del viento y cortafuegos.')], None
    return [], None


def rule_ndvi(ndvi):
    ser = [r for r in ((ndvi or {}).get('series') or []) if r.get('status') == 'válida' and r.get('ndvi_mean') is not None]
    if len(ser) < 2:
        return None, 'menos de dos escenas NDVI válidas'
    a, b = ser[-2], ser[-1]
    drop = a['ndvi_mean'] - b['ndvi_mean']
    if drop >= 0.10:
        return [_alert('vegetacion', 'alta' if drop >= 0.2 else 'media', 'Caída del vigor del pasto',
                       f"NDVI medio bajó de {a['ndvi_mean']:.2f} a {b['ndvi_mean']:.2f} entre {str(a.get('datetime'))[:10]} y {str(b.get('datetime'))[:10]}.",
                       'Sentinel-2 · Planetary Computer', 'Recorrer el potrero: pastoreo, helada, sequía o anegamiento.', str(b.get('datetime'))[:10])], None
    return [], None


def evaluate(lat, lon, polygon=None, known=None):
    known = known or {}
    jobs = {}
    if not (known.get('estadistica') or {}).get('ensemble'):
        import forecast_stats as fs
        jobs['ensemble'] = lambda: fs.ensemble_probs(lat, lon)
    jobs['forecast'] = lambda: c.external('https://api.open-meteo.com/v1/forecast', {
        'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 7,
        'hourly': 'temperature_2m,relative_humidity_2m',
        'daily': 'precipitation_sum,et0_fao_evapotranspiration'})['data']
    if known.get('firms') is None and os.environ.get('FIRMS_MAP_KEY'):
        jobs['firms'] = lambda: c.firms(lat, lon, polygon)['data']
    got, failed = {}, {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {k: pool.submit(f) for k, f in jobs.items()}
        for k, f in futs.items():
            try:
                got[k] = f.result()
            except Exception as e:
                failed[k] = type(e).__name__
    ens = (known.get('estadistica') or {}).get('ensemble') or got.get('ensemble')
    fc = got.get('forecast') or {}
    rules = {
        'helada': lambda: rule_frost(ens),
        'calor': lambda: rule_heat(fc.get('hourly'), ens),
        'lluvia': lambda: rule_rain(ens, fc.get('daily')),
        'sequía': lambda: rule_drought(known.get('lluvia'), fc.get('daily')),
        'fuego': lambda: rule_fire(known.get('firms') if known.get('firms') is not None else got.get('firms')),
        'vegetación': lambda: rule_ndvi(known.get('ndvi')),
    }
    alerts, unevaluated = [], {}
    for name, fn in rules.items():
        res, why = fn()
        if res is None:
            unevaluated[name] = why
        else:
            alerts.extend(res)
    alerts.sort(key=lambda a: -LEVELS[a['level']])
    evaluated = [k for k in rules if k not in unevaluated]
    return c.envelope({'alerts': alerts, 'evaluated': evaluated, 'unevaluated': unevaluated, 'failed_sources': failed,
                       'summary': (f"{len(alerts)} alerta(s) activa(s)" if alerts else 'Sin alertas en las reglas evaluadas')
                                  + f" · {len(evaluated)} de {len(rules)} reglas evaluadas"},
                      'multi', 'alertas del lote', 'DOTS · reglas declaradas sobre fuentes verificadas',
                      'recibido' if evaluated else 'sin dato', None if evaluated else 'Ninguna regla pudo evaluarse')
