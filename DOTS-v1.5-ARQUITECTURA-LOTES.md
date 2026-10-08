# DOTS Campo v1.5 - Arquitectura centrada en lotes

Flujo implementado en interfaz: mapa -> delimitación -> guardado de múltiples lotes -> selección por lote -> análisis DOTS -> informe PDF.

## Reglas
- El lote/potrero es la unidad de contexto. Cada polígono conserva vértices, centroide, superficie y perímetro.
- Los polígonos pueden ser triángulo, rectángulo o polígono libre.
- Al seleccionar un lote, las consultas y el informe usan ese lote como contexto territorial.
- `Analizar lote seleccionado` invoca el backend Agentic existente con el polígono completo y exige no inventar variables faltantes.
- El PDF unificado se genera por `/api/fuentes/analizar` o `/api/fuentes/agentic/pdf` y recibe el polígono.
- NASA GIBS sigue disponible como capa de imagen real. Las fuentes de catálogo no se presentan como raster procesado.

## Pendiente de credenciales
Sentinel Hub, CDS/ERA5 directo, NASA Earthdata, USGS M2M, NOAA CDO, Copernicus Marine, Google Earth Engine y las demás fuentes protegidas permanecen identificadas como `requiere credencial` hasta cargar secretos reales en Vercel.

## Criterio de verdad
Fuente -> producto/sensor -> fecha -> polígono -> variable -> unidad -> método -> estado -> confianza -> interpretación DOTS.
