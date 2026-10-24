"""Diccionario de variables del modelo de barrios populares por radar (scripts/barrios_radar.py).

Una sola lista para la página de consulta, la API y los informes PDF: código, grupo, nombre y qué mide.
"""

ENTRADAS = [
    # Color · Sentinel-2
    ('B2', 'Color · Sentinel-2', 'Azul', 'Reflectancia en el azul. Techos de chapa y hormigón.'),
    ('B3', 'Color · Sentinel-2', 'Verde', 'Reflectancia en el verde.'),
    ('B4', 'Color · Sentinel-2', 'Rojo', 'Reflectancia en el rojo. Tierra y calles sin asfaltar.'),
    ('B8', 'Color · Sentinel-2', 'Infrarrojo cercano', 'Separa vegetación de construcción.'),
    ('B11', 'Color · Sentinel-2', 'Infrarrojo de onda corta 1', 'Materiales de techo y suelo seco.'),
    ('B12', 'Color · Sentinel-2', 'Infrarrojo de onda corta 2', 'Materiales de techo y suelo seco.'),
    ('NDVI', 'Color · Sentinel-2', 'Índice de vegetación', 'Cuánto verde hay: árboles, patios, plazas.'),
    ('NDBI', 'Color · Sentinel-2', 'Índice de construcción', 'Cuánta superficie construida o impermeable hay.'),
    # Radar · Sentinel-1
    ('VV', 'Radar · Sentinel-1', 'Rebote vertical (VV)', 'Fuerza con que vuelve la señal; alta en paredes y techos.'),
    ('VH', 'Radar · Sentinel-1', 'Rebote cruzado (VH)', 'Señal que vuelve girada; sube con formas irregulares.'),
    ('VHVV', 'Radar · Sentinel-1', 'Diferencia VH − VV', 'Relación entre los dos rebotes: tipo de estructura.'),
    ('VV_dry', 'Radar · Sentinel-1', 'Rebote en temporada seca', 'VV de junio a septiembre.'),
    ('VV_wet', 'Radar · Sentinel-1', 'Rebote en temporada húmeda', 'VV de diciembre a marzo.'),
    ('VV_season', 'Radar · Sentinel-1', 'Cambio húmeda − seca', 'Lo construido casi no cambia entre estaciones; el campo sí.'),
    ('VV_tstd', 'Radar · Sentinel-1', 'Variación en el tiempo', 'Cuánto cambia el rebote entre pasadas (construcciones nuevas, obras).'),
    ('VVt_contrast', 'Radar · Sentinel-1', 'Textura VV · contraste', 'Saltos bruscos entre píxeles vecinos.'),
    ('VVt_var', 'Radar · Sentinel-1', 'Textura VV · varianza', 'Qué tan desparejo es el rebote alrededor.'),
    ('VVt_ent', 'Radar · Sentinel-1', 'Textura VV · entropía', 'Desorden: alto en tramas irregulares.'),
    ('VVt_idm', 'Radar · Sentinel-1', 'Textura VV · homogeneidad', 'Regularidad: alta en barrios planificados.'),
    ('VHt_contrast', 'Radar · Sentinel-1', 'Textura VH · contraste', 'Saltos bruscos en el rebote cruzado.'),
    ('VHt_var', 'Radar · Sentinel-1', 'Textura VH · varianza', 'Desparejo del rebote cruzado.'),
    ('VHt_ent', 'Radar · Sentinel-1', 'Textura VH · entropía', 'Desorden del rebote cruzado.'),
    ('VH_diff', 'Radar · Sentinel-1', 'Desorden a escala de manzana', 'Entropía de VH en 7×7 píxeles (unos 70 m).'),
    ('VV_cv3', 'Radar · Sentinel-1', 'Dispersión en 3×3', 'Retornos débiles y desparejos de construcciones chicas, a 30 m.'),
    ('VV_cv5', 'Radar · Sentinel-1', 'Dispersión en 5×5', 'Lo mismo a 50 m.'),
    ('VV_lmean', 'Radar · Sentinel-1', 'Rebote medio en 5×5', 'Nivel general de construcción alrededor.'),
    # Construcciones · Google Open Buildings
    ('BLD_count', 'Construcciones · Google Open Buildings', 'Cantidad de construcciones', 'Cuántas hay en 25 m a la redonda: amontonamiento.'),
    ('BLD_presence', 'Construcciones · Google Open Buildings', 'Presencia de construcciones', 'Qué parte del entorno está construida.'),
    ('BLD_height', 'Construcciones · Google Open Buildings', 'Altura media', 'Altura promedio de lo construido.'),
    ('BLD_hstd', 'Construcciones · Google Open Buildings', 'Variación de alturas', 'Qué tan desparejas son las alturas: alta en barrios populares.'),
]

SALIDAS = [
    ('informal_ha', 'Superficie con firma de barrio popular', 'ha', 'Lo que el modelo marca como barrio popular en 15 km.'),
    ('in_renabap_ha', 'Detectado dentro del RENABAP', 'ha', 'Parte de lo detectado que cae en barrios registrados.'),
    ('a_verificar_ha', 'Zonas a verificar', 'ha', 'Con la misma firma pero fuera del registro: barrios nuevos o errores.'),
    ('renabap_detectado', 'RENABAP reconocido', '%', 'Qué parte de lo construido en barrios registrados reconoce el modelo.'),
    ('renabap_barrios', 'Barrios del RENABAP en la zona', 'barrios', 'Polígonos del registro usados para comparar.'),
    ('pop_informal', 'Personas en zonas detectadas', 'personas', 'WorldPop 2020 sobre las zonas detectadas.'),
    ('pop_informal_hand', 'Personas a 1, 2, 3 y 5 m sobre el río', 'personas', 'Las anteriores según altura sobre el curso de agua (MERIT Hydro).'),
]


def lista(pesos=None):
    """Variables de entrada con su peso en el modelo, si se conoce."""
    w = {p['capa']: p['peso'] for p in (pesos or []) if isinstance(p, dict)}
    return [{'codigo': c, 'grupo': g, 'nombre': n, 'mide': m, 'peso': w.get(c)} for c, g, n, m in ENTRADAS]


def salidas():
    return [{'codigo': c, 'nombre': n, 'unidad': u, 'mide': m} for c, n, u, m in SALIDAS]
