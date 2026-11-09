# DOTS — Atlas histórico y temporal

## Experiencia visual

Una línea de tiempo horizontal, densa y navegable, inspirada en la cronología mundial de 5.000 años de la referencia. El usuario se desplaza y hace zoom conservando el contexto temporal. La vista combina:

- Carriles de acontecimientos históricos y productivos.
- Series de superficie sembrada, cosechada, producción y rendimiento.
- Series climáticas: precipitación, temperatura y anomalías.
- Hitos tecnológicos, territoriales, normativos y de infraestructura.
- Gráficos comparativos y mapas vinculados a la región seleccionada.

## Escalas temporales y rigor

| Escala | Información |
|---|---|
| 5.000 años / milenios | Historia agraria, domesticación y difusión de cultivos, sociedades y grandes hitos; no atribuir cifras anuales inexistentes |
| Siglos / décadas | Reconstrucciones históricas y cambios de uso del suelo con método documentado |
| Años / campañas | Siembra, cosecha, producción, rendimiento, comercio y clima según estadísticas disponibles |
| Meses | Series mensuales publicadas por las fuentes |
| Días | Satélite, estaciones, clima y eventos desde el comienzo real de la cobertura |

El zoom puede recorrer todo el rango, pero el detalle depende de la resolución temporal real de cada fuente. Nunca presentar una serie anual interpolada como observación diaria. Diferenciar dato observado, estimación, pronóstico y reconstrucción.

## Alcance geográfico: Sudamérica

Primera etapa, exclusivamente sudamericana:

1. **Argentina:** país, provincias y regiones productivas; departamentos/partidos cuando las fuentes lo permitan.
2. **Brasil:** país, estados y regiones productivas; municipios cuando las fuentes lo permitan.
3. **Uruguay:** país, departamentos y regiones productivas.
4. **Paraguay:** país, departamentos y regiones productivas.

La arquitectura permitirá incorporar gradualmente otros países de Sudamérica cuando se definan prioridades y fuentes. No incluir Europa ni otras regiones fuera del alcance acordado.

## Indicadores agrícolas

- Superficie sembrada (ha).
- Superficie cosechada (ha).
- Producción (t).
- Rendimiento (kg/ha o t/ha).
- Cultivo, campaña, jurisdicción y metodología.
- Fecha de publicación y revisión estadística.

No mezclar campaña agrícola con año calendario sin explicitar la conversión. Mantener los valores originales y sus unidades.

## Fuentes prioritarias por cobertura

- **Argentina:** MAGyP/SIIA, INDEC, estadísticas provinciales y bolsas de cereales como fuentes complementarias identificadas.
- **Brasil:** IBGE, CONAB, MAPA y estadísticas oficiales estatales.
- **Uruguay:** MGAP, DIEA e INE.
- **Paraguay:** MAG, INE y estadísticas oficiales agropecuarias.
- **Comparación regional:** FAOSTAT y CEPAL, con metadatos para armonizar definiciones.
- **Clima:** SMN y servicios meteorológicos nacionales, NASA POWER, ERA5 y CHIRPS según variable y resolución.
- **Satélite:** Landsat, MODIS, Sentinel y SAOCOM/CONAE según producto y cobertura.

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
    "admin1": "Buenos Aires",
    "admin2": null
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

El cero del ejemplo es un marcador de esquema, no una observación real.

## Interacción entre cronología, gráficos y mapa

- Seleccionar un país o jurisdicción actualiza los carriles, gráficos y mapa.
- Seleccionar un cultivo filtra siembra, cosecha, producción y rendimiento.
- Seleccionar un intervalo temporal actualiza todas las vistas relacionadas.
- Seleccionar un hito abre su ficha, fecha, territorio y referencias.
- Comparar regiones utiliza unidades y escalas explícitas.
- Cada gráfico informa fuente, cobertura, resolución y faltantes.

## Criterios de aceptación

- Zoom fluido desde milenios hasta días, sin fingir resolución inexistente.
- Cobertura inicial de Argentina, Brasil, Uruguay y Paraguay.
- Argentina: primera vista provincial productiva; Buenos Aires incluida.
- Comparación de provincias, estados, departamentos y regiones según cobertura estadística.
- Gráficos vinculados a cronología y mapa.
- Fuentes, fechas de actualización y metodología visibles.
- Datos faltantes y estimaciones claramente diferenciados.
- Exportación de gráficos e informes con referencias.
