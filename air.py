"""air v1.0 — calidad de aire interpretada (esencia de OpenAQ / CAMS).

Toma los contaminantes que trae Open-Meteo (CAMS): PM2.5, PM10, O₃, NO₂, SO₂ y CO, calcula el índice
europeo de calidad del aire (EAQI) por contaminante y global, y agrega una lectura agronómica (ozono
que daña cultivos sensibles, partículas por quema o labranza). Los valores de CAMS son de modelo en
grilla, no de una estación de medición; para medición real se usa la API de OpenAQ (requiere clave).
"""

# Tramos del índice europeo (µg/m³ excepto CO en mg/m³) y su índice asociado.
BREAKPOINTS = {
    'pm2_5': [0, 10, 20, 25, 50, 75, 800],
    'pm10': [0, 20, 40, 50, 100, 150, 1200],
    'nitrogen_dioxide': [0, 40, 90, 120, 230, 340, 1000],
    'ozone': [0, 50, 100, 130, 240, 380, 800],
    'sulphur_dioxide': [0, 100, 200, 350, 500, 750, 1250],
    'carbon_monoxide': [0, 4, 10, 20, 35, 55, 150],
}
INDEX = [0, 20, 40, 60, 80, 100, 500]
LABELS = {'pm2_5': 'PM2,5', 'pm10': 'PM10', 'nitrogen_dioxide': 'NO₂', 'ozone': 'O₃',
          'sulphur_dioxide': 'SO₂', 'carbon_monoxide': 'CO'}


def category(a):
    if a is None:
        return 'sin dato'
    if a <= 20:
        return 'buena'
    if a <= 40:
        return 'aceptable'
    if a <= 60:
        return 'moderada'
    if a <= 80:
        return 'mala'
    if a <= 100:
        return 'muy mala'
    return 'extremadamente mala'


def sub_index(v, bps, idx=INDEX):
    """Subíndice de un contaminante por interpolación lineal dentro del tramo."""
    if v is None:
        return None
    if v <= bps[0]:
        return 0
    for i in range(1, len(bps)):
        if v <= bps[i]:
            lo_b, hi_b, lo_i, hi_i = bps[i - 1], bps[i], idx[i - 1], idx[i]
            return round(lo_i + (v - lo_b) / (hi_b - lo_b) * (hi_i - lo_i))
    return idx[-1]


def mean(values, n=24):
    xs = [v for v in (values or [])[:n] if v is not None]
    return sum(xs) / len(xs) if xs else None


def from_open_meteo(hourly, n=24):
    """Concentraciones medias de las próximas n horas desde el bloque hourly de Open-Meteo."""
    return {k: mean((hourly or {}).get(k), n) for k in BREAKPOINTS}


def evaluate(pollutants):
    """pollutants: {'pm2_5': µg/m³, ..., 'carbon_monoxide': µg/m³}. CO se pasa a mg/m³."""
    per = {}
    for key, bps in BREAKPOINTS.items():
        v = pollutants.get(key)
        if key == 'carbon_monoxide' and v is not None and v > 100:   # Open-Meteo entrega CO en µg/m³
            v = v / 1000.0
        per[key] = {'label': LABELS[key], 'value': None if v is None else round(v, 1), 'sub_index': sub_index(v, bps)}
    subs = [x['sub_index'] for x in per.values() if x['sub_index'] is not None]
    overall = max(subs) if subs else None
    notes = []
    if (per['ozone']['sub_index'] or 0) >= 60:
        notes.append('ozono alto: puede dañar cultivos sensibles')
    if (per['pm10']['sub_index'] or 0) >= 50:
        notes.append('muchas partículas: posible humo, quema o labranza')
    if overall is not None and overall <= 20 and not notes:
        notes.append('aire en buen estado')
    reading = (f"Índice europeo de calidad del aire {overall} ({category(overall)})"
               + ('. ' + '; '.join(notes) + '.' if notes else '.') if overall is not None
               else 'Sin dato de calidad de aire.')
    return {'index': overall, 'category': category(overall), 'per_pollutant': per, 'reading': reading}
