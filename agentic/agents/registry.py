"""DOTS research agents: responsibilities, cadence and evidence contracts.

This registry defines work ownership. It does not claim a source is connected
until its adapter has been implemented and its last successful run recorded.
"""
AGENTS = {
    "coordinator": {
        "name": "Coordinador DOTS",
        "role": "Planificar ciclos, asignar tareas, resolver dependencias y consolidar resultados.",
        "cadence": "cada ciclo",
        "inputs": ["estado_de_agentes", "cola_de_tareas", "alertas_de_calidad"],
        "outputs": ["plan_de_trabajo", "estado_general", "resumen_diario"],
    },
    "agricultural_history": {
        "name": "Agente de Historia Agrícola",
        "role": "Construir series históricas de cultivos, superficie sembrada, cosechada, producción y rendimiento.",
        "cadence": "mensual y ante nueva publicación",
        "sources": ["FAOSTAT", "MAGyP/SIIA", "INDEC", "Bolsas de Cereales"],
        "outputs": ["series_agricolas", "hitos_historicos", "fichas_de_fuente"],
    },
    "climate": {
        "name": "Agente Climático",
        "role": "Recolectar y comparar precipitación, temperatura, humedad, sequía y anomalías.",
        "cadence": "diario; consolidación mensual",
        "sources": ["SMN", "NASA POWER", "ERA5", "CHIRPS", "NOAA"],
        "outputs": ["series_climaticas", "anomalias", "eventos_extremos"],
    },
    "satellite": {
        "name": "Agente Satelital y Vegetación",
        "role": "Procesar cobertura, NDVI/EVI, cambios de uso y observaciones Sentinel/Landsat/MODIS.",
        "cadence": "según nueva escena disponible",
        "sources": ["Sentinel-2", "Sentinel-1", "Landsat", "MODIS", "SAOCOM/CONAE"],
        "outputs": ["observaciones_raster", "series_vegetacion", "cambios_territoriales"],
    },
    "water": {
        "name": "Agente Hidrológico",
        "role": "Seguir lluvias, humedad, caudales, inundaciones y sequías hidrológicas.",
        "cadence": "diario; mayor frecuencia ante eventos",
        "sources": ["INA", "GloFAS", "Copernicus", "NASA"],
        "outputs": ["series_hidrologicas", "eventos_de_agua", "alertas_territoriales"],
    },
    "territorial": {
        "name": "Agente Territorial",
        "role": "Organizar indicadores por país, provincia, partido, cuenca y región productiva.",
        "cadence": "semanal y ante nueva cartografía",
        "sources": ["cartografía oficial", "INDEC", "MAGyP", "WorldPop"],
        "outputs": ["indicadores_geograficos", "capas", "comparaciones_regionales"],
    },
    "market": {
        "name": "Agente de Mercados Agropecuarios",
        "role": "Seguir precios, comercio exterior, exportaciones y contexto de mercados.",
        "cadence": "diario o según publicación",
        "sources": ["MAGyP", "INDEC", "Comtrade", "fuentes oficiales de mercado"],
        "outputs": ["series_de_mercado", "comercio_exterior", "contexto_de_precios"],
    },
    "historical_timeline": {
        "name": "Agente de Línea de Tiempo",
        "role": "Normalizar hitos y series en escalas temporales; enlazar hechos con datos y territorio.",
        "cadence": "cada vez que cambia una serie o se valida un hito",
        "inputs": ["series_agricolas", "series_climaticas", "eventos_de_agua", "hitos_historicos"],
        "outputs": ["timeline_events", "timeline_series", "marcas_de_fuente"],
    },
    "quality_auditor": {
        "name": "Agente de Calidad y Auditoría",
        "role": "Validar unidades, cobertura, fechas, revisiones, duplicados, faltantes y procedencia.",
        "cadence": "antes de publicar cada resultado",
        "outputs": ["quality_report", "publication_decision", "warnings"],
    },
    "analyst_reporter": {
        "name": "Agente Analista y Redactor",
        "role": "Detectar variaciones y relaciones; redactar informes con evidencia y límites explícitos.",
        "cadence": "diario y ante eventos relevantes",
        "outputs": ["daily_brief", "regional_reports", "charts", "citations"],
    },
}

# Only agents whose data adapters and scheduled runners have been tested may
# be marked active by runtime state. Registry presence means defined, not live.
DEFAULT_AGENT_STATE = "defined"
