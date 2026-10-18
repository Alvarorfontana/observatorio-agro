"""disease v1.0 — riesgo de enfermedad por clima (idea de xarvio / modelos de infección tipo Smith).

Un patógeno necesita, para infectar, horas de mojado foliar dentro de una franja de temperatura. Cada
enfermedad tiene su franja, su temperatura óptima y las horas de mojado que exige; el modelo cuenta las
horas favorables del pronóstico y las pondera por cuán cerca está la temperatura del óptimo. Devuelve un
índice de riesgo 0-100 con su escala (mínimo, máximo y bandas) y el día donde conviene mirar el lote.

Es ORIENTATIVO: anticipa presión de enfermedad a partir del clima, no reemplaza el monitoreo ni el
umbral de daño económico de cada cultivo. No considera resistencia varietal, inóculo presente ni fungicidas.
"""
import scales

try:
    from spray_window import wet_bulb   # reutiliza la fórmula de Stull para la humedad
except Exception:                        # pragma: no cover
    wet_bulb = None

# Franja de temperatura de infección, óptimo y horas de mojado foliar que exige cada enfermedad.
DISEASES = {
    'trigo_roya':     {'name': 'Roya de la hoja (trigo)', 'crop': 'trigo', 'tmin': 10, 'tmax': 25, 'opt': (15, 22), 'wet_h': 4, 'splash': False},
    'trigo_septoria': {'name': 'Septoria (trigo)',        'crop': 'trigo', 'tmin': 5,  'tmax': 22, 'opt': (10, 18), 'wet_h': 6, 'splash': True},
    'trigo_fusarium': {'name': 'Fusariosis de la espiga (trigo)', 'crop': 'trigo', 'tmin': 15, 'tmax': 30, 'opt': (20, 28), 'wet_h': 6, 'splash': True},
    'maiz_tizon':     {'name': 'Tizón foliar (maíz)',     'crop': 'maiz',  'tmin': 18, 'tmax': 32, 'opt': (22, 30), 'wet_h': 6, 'splash': False},
    'maiz_roya':      {'name': 'Roya común (maíz)',       'crop': 'maiz',  'tmin': 15, 'tmax': 30, 'opt': (20, 28), 'wet_h': 4, 'splash': False},
    'papa_tizon':     {'name': 'Tizón tardío (papa)',     'crop': 'papa',  'tmin': 10, 'tmax': 24, 'opt': (15, 20), 'wet_h': 4, 'splash': False},
    'soja_roya':      {'name': 'Roya asiática (soja)',    'crop': 'soja',  'tmin': 15, 'tmax': 28, 'opt': (18, 26), 'wet_h': 6, 'splash': False},
}
BY_CROP = {'trigo': ['trigo_roya', 'trigo_septoria', 'trigo_fusarium'], 'maiz': ['maiz_tizon', 'maiz_roya'],
           'papa': ['papa_tizon'], 'soja': ['soja_roya']}
WET_RH = 90.0      # % de humedad que cuenta como mojado foliar
WET_RAIN = 0.2     # mm/h que cuenta como mojado foliar


def catalog():
    """Enfermedades disponibles con su franja térmica y su escala de riesgo."""
    return [{**{'key': k, **d}, 'risk_scale': scales.describe('disease_risk')} for k, d in DISEASES.items()]


def favourability(t, d):
    """0 a 1 según cuán cerca está la temperatura de la franja y del óptimo de la enfermedad."""
    if t is None or not (d['tmin'] <= t <= d['tmax']):
        return 0.0
    lo, hi = d['opt']
    if lo <= t <= hi:
        return 1.0
    if t < lo:
        return 0.2 + 0.8 * (t - d['tmin']) / ((lo - d['tmin']) or 1)
    return 0.2 + 0.8 * (d['tmax'] - t) / ((d['tmax'] - hi) or 1)


def evaluate(hourly, disease='trigo_septoria', days=7):
    """hourly: dict de Open-Meteo. Devuelve riesgo por día con su escala."""
    d = DISEASES.get(disease)
    if not d:
        raise ValueError(f'Enfermedad desconocida: {disease} (opciones: {", ".join(DISEASES)})')
    t = (hourly or {}).get('time') or []
    temp = (hourly or {}).get('temperature_2m') or []
    rh = (hourly or {}).get('relative_humidity_2m') or []
    rain = (hourly or {}).get('precipitation') or []
    if not t or not temp:
        raise ValueError('Sin pronóstico horario para estimar el riesgo de enfermedad')

    per_day = {}
    for i in range(len(t)):
        tp = temp[i] if i < len(temp) else None
        hr = rh[i] if i < len(rh) else None
        rn = rain[i] if i < len(rain) else None
        day = str(t[i])[:10]
        e = per_day.setdefault(day, {'wet_h': 0, 'wet_range_h': 0, 'favor_sum': 0.0, 'temps': [], 'rain_mm': 0.0})
        wet = (hr is not None and hr >= WET_RH) or (rn is not None and rn >= WET_RAIN)
        if tp is not None:
            e['temps'].append(tp)
        if rn:
            e['rain_mm'] += rn
        if wet:
            e['wet_h'] += 1
            f = favourability(tp, d)
            if f > 0:
                e['wet_range_h'] += 1
                e['favor_sum'] += f

    rows = []
    required = d['wet_h']
    for day in sorted(per_day)[:days]:
        e = per_day[day]
        mean_t = round(sum(e['temps']) / len(e['temps']), 1) if e['temps'] else None
        ratio = min(1.0, e['favor_sum'] / required) if required else 0.0
        risk = round(100 * ratio)
        b = scales.band('disease_risk', risk)
        rows.append({'date': day, 'mean_temp_c': mean_t, 'wet_hours': e['wet_h'], 'wet_hours_in_range': e['wet_range_h'],
                     'rain_mm': round(e['rain_mm'], 1), 'risk': risk, 'band': {'label': b['label'], 'tone': b['tone']}})
    if not rows:
        raise ValueError('El pronóstico no cubre ningún día completo')
    top = max(rows, key=lambda r: r['risk'])
    return {'disease': disease, 'name': d['name'], 'crop': d['crop'], 'rows': rows, 'days': len(rows),
            'risk_max': top['risk'], 'risk_max_date': top['date'], 'wet_hours_required': required,
            'temperature_range_c': [d['tmin'], d['tmax']], 'temperature_optimum_c': list(d['opt']),
            'scale': scales.describe('disease_risk'), 'thresholds': {'mojado_rh_pct': WET_RH, 'mojado_lluvia_mm_h': WET_RAIN},
            'reading': reading(rows, d, required)}


def reading(rows, d, required):
    top = max(rows, key=lambda r: r['risk'])
    if top['risk'] < 20:
        return f"{d['name']}: riesgo bajo en el pronóstico (máximo {top['risk']}/100 el {top['date']})."
    return (f"{d['name']}: riesgo {top['band']['label']} el {top['date']} ({top['risk']}/100); "
            f"{top['wet_hours_in_range']} hora(s) de mojado en franja frente a {required} que pide el patógeno. "
            'Recorrer el lote y comparar con el umbral de daño del cultivo antes de decidir un fungicida.')


def advise(lat, lon, disease='trigo_septoria', days=7):
    """Trae el horario de Open-Meteo y devuelve el riesgo de enfermedad por día."""
    import research_connectors as c
    env = c.external('https://api.open-meteo.com/v1/forecast',
                     {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': max(days, 3),
                      'hourly': 'temperature_2m,relative_humidity_2m,precipitation'})
    data = evaluate((env.get('data') or {}).get('hourly') or {}, disease, days)
    data['point'] = {'lat': lat, 'lon': lon}
    return c.envelope(data, env.get('source_url'), 'riesgo de enfermedad por clima',
                      'Open-Meteo · modelo de infección por mojado foliar', 'recibido',
                      None)
