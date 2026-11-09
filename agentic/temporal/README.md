# DOTS — Atlas histórico y temporal

## Experiencia visual requerida

Una línea de tiempo horizontal, densa y navegable, inspirada en las grandes cronologías históricas de 5.000 años. El usuario puede desplazarse y hacer zoom sin perder el contexto temporal. La vista combina:

- carriles de acontecimientos históricos y productivos;
- series cuantitativas de superficie sembrada, superficie cosechada, producción y rendimiento;
- series climáticas: precipitación, temperatura y anomalías;
- hitos territoriales, tecnológicos, normativos y de infraestructura;
- gráficos comparativos y mapas vinculados a la región seleccionada.

## Escalas y límites reales de resolución

| Escala visible | Contenido admisible |
|---|---|
| 5.000 años / milenios | Cronología histórica, domesticación, difusión de cultivos, sociedades agrarias y grandes hitos; no atribuir cifras anuales inexistentes |
| Siglos / décadas | Cambios de uso del suelo, expansión agrícola, censos y reconstrucciones históricas con método documentado |
| Años | Series oficiales de siembra, cosecha, producción, rendimiento, comercio y clima |
| Meses | Series mensuales cuando la fuente las publique; clima, precios y campañas |
| Días | Observaciones diarias, satélite, estaciones, pronósticos y eventos sólo desde la fecha de cobertura real de cada fuente |

El zoom visual puede recorrer todo el rango, pero el detalle que aparece depende de la resolución temporal de los datos. Nunca interpolar una serie anual para presentarla como observación diaria.

## Regiones iniciales

1. Provincia de Buenos Aires: provincia completa, con desglose por partido cuando la fuente lo permita.
2. Argentina y regiones productivas: comparación nacional y entre provincias.
3. Península ibérica e itálica: módulos comparativos de territorio, agricultura y clima, siempre sujetos a disponibilidad y armonización de fuentes oficiales.
4. Escala global: hitos de historia agrícola y series comparables internacionales.

## Indicadores agrícolas

- Superficie sembrada (ha).
- Superficie cosechada (ha).
- Producción (t).
- Rendimiento (kg/ha o t/ha).
- Cultivo, campaña, jurisdicción y metodología.
- Fecha de publicación y revisión de la estadística.

No mezclar campaña agrícola con año calendario sin explicitar la conversión. Mantener cultivos y unidades comparables.

## Fuentes prioritarias a integrar y verificar

- Argentina: MAGyP / SIIA, INDEC y estadísticas provinciales; bolsas de cereales como fuente complementaria, identificando su carácter.
- Internacional: FAOSTAT para cultivos y países; Eurostat y estadísticas nacionales para España e Italia.
- Clima: SMN, NASA POWER, ERA5 y CHIRPS según variable y resolución.
- Satélite: Landsat, MODIS, Sentinel y SAOCOM/CONAE según producto y cobertura.

Una fuente documentada no equivale a un conector operativo. Cada integración debe registrar endpoint, licencia, cobertura, frecuencia, unidades, última consulta y prueba de actualización.

## Contrato mínimo de cada observación

```json
{
  "series_id": "ar-buenos-aires-soja-area-sembrada",
  "indicator": "area_sown",
  "value": 0,
  "unit": "ha",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "temporal_resolution": "campaign",
  "geography": {
    "country": "AR",
    "province": "Buenos Aires",
    "admin_level": 1
  },
  "crop": "soybean",
  "source": "official-source-id",
  "source_url": "https://...",
  "published_at": "YYYY-MM-DD",
  "retrieved_at": "ISO-8601",
  "methodology": "source-defined",
  "status": "observed",
  "revision": null
}
```

El cero del ejemplo es un marcador de esquema, no una observación. Los datos productivos deben almacenarse sin redondeo prematuro y con su valor original.

## Interacción entre gráfico, mapa y cronología

- Seleccionar una provincia/país actualiza los carriles y gráficos.
- Seleccionar un cultivo filtra siembra, cosecha, producción y rendimiento.
- Seleccionar un intervalo temporal actualiza el mapa y las series.
- Seleccionar un hito abre su ficha, fecha, territorio y referencias.
- Comparar regiones usa escalas y unidades explícitas.
- Cada gráfico informa fuente, cobertura, resolución y faltantes.

## Criterios de aceptación

- Zoom y desplazamiento fluidos desde milenios hasta días.
- Cambio de granularidad sin fingir resolución inexistente.
- Provincia de Buenos Aires como primera región productiva.
- Vistas comparativas ibérica e itálica.
- Gráficos vinculados a la cronología y al mapa.
- Fuentes y fecha de actualización visibles.
- Datos faltantes y estimaciones claramente diferenciados.
- Exportación de gráficos e informe con metodología y referencias.
