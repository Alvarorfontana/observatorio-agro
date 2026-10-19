"""scales v1.0 — escala de valores de cada indicador DOTS.

Todo número que DOTS muestra viaja con su escala declarada: el rango físicamente posible (mínimo y
máximo), los cortes que separan las bandas y la banda en la que cae el valor. Un dato sin escala no
es interpretable: 0,6 de NDVI no dice nada hasta saber que el rango va de -1 a 1 y que 0,5 es "vigor
alto". Esto es lo que exige un informe técnico y lo que permite comparar lotes, campañas y regiones.

`band(escala, valor)` devuelve el valor con su escala, su banda y su tono; `describe(escala)` devuelve
la escala sola (para leyendas y ejes de gráficos); `all_scales()` lista todo el catálogo.

Tono ∈ {'ok', 'warn', 'risk', 'idle'} — los mismos que usa el informe DOTS.
Dirección ∈ {'high_ok' (más es mejor), 'low_ok' (menos es mejor), 'band' (óptimo en el medio)}.
"""

# Cada banda es (corte_superior_exclusivo, etiqueta, tono); la última captura todo lo que queda.
SCALES = {
    'ndvi': {'name': 'Índice de vegetación NDVI', 'unit': '', 'min': -1.0, 'max': 1.0, 'direction': 'high_ok',
             'bands': [(0.20, 'suelo desnudo o muy bajo', 'risk'), (0.35, 'vigor bajo', 'warn'),
                       (0.50, 'vigor medio', 'idle'), (0.70, 'vigor alto', 'ok'), (1.01, 'vigor muy alto', 'ok')],
             'bands_labels': ['< 0,20', '0,20–0,35', '0,35–0,50', '0,50–0,70', '> 0,70']},
    'ndmi': {'name': 'Índice de humedad del follaje NDMI', 'unit': '', 'min': -1.0, 'max': 1.0, 'direction': 'band',
             'bands': [(-0.05, 'estrés hídrico marcado', 'risk'), (0.10, 'follaje seco', 'warn'),
                       (0.30, 'humedad normal', 'ok'), (1.01, 'follaje muy húmedo', 'ok')],
             'bands_labels': ['< -0,05', '-0,05–0,10', '0,10–0,30', '> 0,30']},
    'spi': {'name': 'Índice estandarizado de precipitación SPI', 'unit': '', 'min': -3.0, 'max': 3.0, 'direction': 'high_ok',
            'bands': [(-2.0, 'sequía extrema', 'risk'), (-1.5, 'sequía severa', 'risk'), (-1.0, 'sequía moderada', 'warn'),
                      (1.0, 'normal', 'ok'), (1.5, 'húmedo', 'ok'), (2.0, 'muy húmedo', 'ok'), (3.01, 'extremadamente húmedo', 'ok')],
            'bands_labels': ['< -2', '-2 a -1,5', '-1,5 a -1', '-1 a 1', '1 a 1,5', '1,5 a 2', '> 2']},
    'thi': {'name': 'Índice de temperatura y humedad THI (rodeo)', 'unit': '', 'min': 0.0, 'max': 110.0, 'direction': 'low_ok',
            'bands': [(72.0, 'confort', 'ok'), (79.0, 'alerta por calor', 'warn'), (84.0, 'peligro', 'risk'), (110.1, 'emergencia', 'risk')],
            'bands_labels': ['< 72', '72–79', '79–84', '> 84']},
    'eaqi': {'name': 'Índice europeo de calidad del aire', 'unit': '', 'min': 0.0, 'max': 500.0, 'direction': 'low_ok',
             'bands': [(20.0, 'buena', 'ok'), (40.0, 'aceptable', 'ok'), (60.0, 'moderada', 'warn'),
                       (80.0, 'mala', 'risk'), (100.0, 'muy mala', 'risk'), (500.1, 'extremadamente mala', 'risk')],
             'bands_labels': ['0–20', '20–40', '40–60', '60–80', '80–100', '> 100']},
    'soil_water_pct': {'name': 'Agua útil del suelo', 'unit': '% de la capacidad', 'min': 0.0, 'max': 100.0, 'direction': 'band',
                       'bands': [(20.0, 'déficit severo', 'risk'), (40.0, 'déficit', 'warn'), (70.0, 'adecuada', 'ok'),
                                 (90.0, 'abundante', 'ok'), (100.1, 'saturada', 'warn')],
                       'bands_labels': ['< 20', '20–40', '40–70', '70–90', '> 90']},
    'wind_kph': {'name': 'Velocidad del viento', 'unit': 'km/h', 'min': 0.0, 'max': 60.0, 'direction': 'band',
                 'bands': [(3.0, 'muy calmo: inversión y deriva', 'risk'), (11.0, 'óptimo para pulverizar', 'ok'),
                           (16.0, 'ventoso: deriva', 'warn'), (60.1, 'no pulverizar', 'risk')],
                 'bands_labels': ['< 3', '3–11', '11–16', '> 16']},
    'delta_t': {'name': 'Delta T (temperatura − bulbo húmedo)', 'unit': '°C', 'min': 0.0, 'max': 20.0, 'direction': 'band',
                'bands': [(2.0, 'condensación / inversión', 'risk'), (8.0, 'óptimo de pulverización', 'ok'),
                          (10.0, 'evaporación alta', 'warn'), (20.1, 'demasiado seco: no pulverizar', 'risk')],
                'bands_labels': ['< 2', '2–8', '8–10', '> 10']},
    'spray_index': {'name': 'Aptitud de pulverización', 'unit': '/ 100', 'min': 0.0, 'max': 100.0, 'direction': 'high_ok',
                    'bands': [(40.0, 'no pulverizar', 'risk'), (70.0, 'marginal', 'warn'), (100.1, 'ventana apta', 'ok')],
                    'bands_labels': ['< 40', '40–70', '> 70']},
    'leaf_wetness_h': {'name': 'Horas de mojado foliar', 'unit': 'h', 'min': 0.0, 'max': 24.0, 'direction': 'low_ok',
                       'bands': [(4.0, 'insuficiente para infección', 'ok'), (6.0, 'borde', 'warn'),
                                 (24.1, 'favorable para infección', 'risk')],
                       'bands_labels': ['< 4', '4–6', '> 6']},
    'disease_risk': {'name': 'Riesgo de enfermedad por clima', 'unit': '/ 100', 'min': 0.0, 'max': 100.0, 'direction': 'low_ok',
                     'bands': [(20.0, 'bajo', 'ok'), (40.0, 'moderado', 'warn'), (70.0, 'alto', 'risk'), (100.1, 'muy alto', 'risk')],
                     'bands_labels': ['< 20', '20–40', '40–70', '> 70']},
    'gdd': {'name': 'Grados día de crecimiento', 'unit': '°C·día', 'min': 0.0, 'max': 2000.0, 'direction': 'high_ok',
            'bands': [(200.0, 'implantación', 'idle'), (800.0, 'desarrollo', 'idle'), (1400.0, 'encañazón o floración', 'idle'),
                      (2000.1, 'llenado', 'idle')],
            'bands_labels': ['0–200', '200–800', '800–1400', '> 1400']},
    'caudal_percentil': {'name': 'Percentil de caudal del río', 'unit': '%', 'min': 0.0, 'max': 100.0, 'direction': 'low_ok',
                         'bands': [(25.0, 'muy bajo', 'ok'), (50.0, 'bajo lo normal', 'ok'), (75.0, 'normal a alto', 'warn'),
                                   (90.0, 'muy alto', 'risk'), (100.1, 'extraordinario', 'risk')],
                         'bands_labels': ['< 25', '25–50', '50–75', '75–90', '> 90']},
    'rio_nivel_pct': {'name': 'Altura del río sobre el nivel de alerta', 'unit': '% de la alerta', 'min': 0.0,
                      'max': 150.0, 'direction': 'low_ok',
                      'bands': [(70.0, 'muy por debajo de la alerta', 'ok'), (90.0, 'cerca de la alerta', 'warn'),
                                (100.0, 'en alerta', 'risk'), (150.1, 'sobre el nivel de evacuación', 'risk')],
                      'bands_labels': ['< 70', '70–90', '90–100', '> 100']},
    'flood_rp_years': {'name': 'Período de retorno del primer anegamiento', 'unit': 'años', 'min': 0.0, 'max': 500.0,
                       'direction': 'low_ok',
                       'bands': [(10.5, 'crecida frecuente (10 años)', 'risk'), (20.5, 'cada ~20 años', 'risk'),
                                 (50.5, 'cada ~50 años', 'warn'), (100.5, 'cada ~100 años', 'warn'),
                                 (200.5, 'cada ~200 años', 'idle'), (500.5, 'sólo en crecidas extremas (≥500 años)', 'ok')],
                       'bands_labels': ['10 años', '20 años', '50 años', '100 años', '200 años', '500 años o nunca']},
    'flood_depth_m': {'name': 'Profundidad de inundación (modelo JRC)', 'unit': 'm', 'min': 0.0, 'max': 10.0,
                      'direction': 'low_ok',
                      'bands': [(0.05, 'sin anegamiento', 'ok'), (0.5, 'anegamiento somero', 'warn'),
                                (1.5, 'agua a la altura de una persona', 'risk'), (10.1, 'inundación severa', 'risk')],
                      'bands_labels': ['0', '< 0,50', '0,50–1,50', '> 1,50']},
    'soil_moisture_vwc': {'name': 'Humedad volumétrica del suelo (SMAP)', 'unit': 'm³/m³', 'min': 0.0, 'max': 0.9,
                          'direction': 'band',
                          'bands': [(0.10, 'seco', 'risk'), (0.20, 'bajo', 'warn'), (0.35, 'normal', 'ok'),
                                    (0.50, 'húmedo', 'ok'), (0.91, 'saturado', 'warn')],
                          'bands_labels': ['< 0,10', '0,10–0,20', '0,20–0,35', '0,35–0,50', '> 0,50']},
    'soil_moisture_pctl': {'name': 'Percentil de humedad del suelo (zona de raíces)', 'unit': '%', 'min': 0.0,
                           'max': 100.0, 'direction': 'band',
                           'bands': [(10.0, 'muy seco respecto de lo normal', 'risk'), (30.0, 'más seco que lo normal', 'warn'),
                                     (70.0, 'normal', 'ok'), (90.0, 'más húmedo que lo normal', 'warn'),
                                     (100.1, 'muy húmedo respecto de lo normal', 'risk')],
                           'bands_labels': ['< 10', '10–30', '30–70', '70–90', '> 90']},
    'yield_pct': {'name': 'Rendimiento esperado sobre el potencial', 'unit': '% del potencial', 'min': 0.0,
                  'max': 100.0, 'direction': 'high_ok',
                  'bands': [(50.0, 'riesgo por déficit hídrico', 'risk'), (70.0, 'bajo', 'warn'),
                            (90.0, 'bueno', 'ok'), (100.1, 'cercano al potencial', 'ok')],
                  'bands_labels': ['< 50', '50–70', '70–90', '> 90']},
}


def describe(scale_id):
    """La escala sola (etiquetas de banda incluidas), sin valor: para leyendas y ejes."""
    s = SCALES.get(scale_id)
    if not s:
        return None
    return {'scale': scale_id, 'name': s['name'], 'unit': s['unit'], 'min': s['min'], 'max': s['max'],
            'direction': s['direction'],
            'bands': [{'label': lab, 'range': rng, 'tone': tone} for (_, lab, tone), rng in zip(s['bands'], s['bands_labels'])]}


def band(scale_id, value):
    """Valor con su escala, su banda y su tono. `position` es el lugar 0-100 dentro del rango mínimo-máximo."""
    d = describe(scale_id)
    if d is None:
        return None
    d['value'] = None if value is None else round(float(value), 3)
    if d['value'] is None:
        d.update(label='sin dato', tone='idle', position=None)
        return d
    v = d['value']
    s = SCALES[scale_id]
    d['label'], d['tone'] = next(((lab, tn) for up, lab, tn in s['bands'] if v < up), s['bands'][-1][1:3])
    span = s['max'] - s['min']
    d['position'] = round(100 * (v - s['min']) / span) if span else None
    return d


def clamp(scale_id, value):
    """Recorta un valor al rango declarado de la escala (evita posiciones fuera de 0-100)."""
    s = SCALES.get(scale_id)
    if s is None or value is None:
        return value
    return min(max(float(value), s['min']), s['max'])


def all_scales():
    """Catálogo completo, ordenado por nombre, para el endpoint de transparencia."""
    return [describe(k) for k in sorted(SCALES)]


def ids():
    return sorted(SCALES)
