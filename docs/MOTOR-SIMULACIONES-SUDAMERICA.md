# DOTS Campo · Motor extensible para América del Sur

## Alcance
Argentina, Bolivia, Brasil, Chile, Colombia, Ecuador, Guyana, Paraguay, Perú, Surinam, Uruguay y Venezuela. La región espacial inicial se expresa como bbox (-82,-57,-34,14); esto es una envolvente, **no** una máscara administrativa ni una garantía de cobertura por proveedor. Guayana Francesa requiere tratarse explícitamente como territorio adicional. Para polígonos de parcelas, cuencas y fronteras se requiere una etapa de recorte espacial aún pendiente.

## Arquitectura implementada en esta rama
- `environmentalTimeline.ts`: fotogramas fechados, con fuente, formato y tipo observado/pronóstico/escenario; identificadores extensibles.
- `environmentalCatalog.ts`: 12 experiencias temáticas, con limitaciones y fuentes candidatas.
- `environmentalVariables.ts`: 32 variables registrables, unidades y soporte espacial.
- `environmentalEngine.ts`: registro de variables, adaptadores de proveedores y ejecutores de modelos; valida solicitudes y fechas, filtra y ordena observaciones, rechaza modelos no implementados y datos faltantes.
- `EnvironmentalLab.tsx`: selector inicial de experiencias y control temporal; **aún no integrado** al mapa principal.

## Flujo técnico
1. Usuario selecciona zona (bbox ahora, polígono después), período, variables y producto.
2. Adaptadores de fuente consultan STAC/OGC/APIs oficiales con credenciales y cuotas configuradas del lado servidor.
3. Normalización: CRS, resolución, cobertura, nodata, fecha, unidad, metadatos, licencia.
4. Datos observados -> escenas georreferenciadas -> serie temporal -> visualización y estadísticas.
5. Simulaciones físicas/estadísticas: ejecutor separado con parámetros, calibración, incertidumbre y versión.
6. Resultados: capas, gráfico, exportaciones y trazabilidad.

## Modelos candidatos, NO implementados
- Inundación: detección radar + topografía + caudal + hidrodinámica para pronóstico.
- Sequía: SPI/SPEI y balances hídricos con series suficientemente largas.
- Incendio: propagación con combustible, humedad, topografía y meteorología.
- Cultivos: índices de vigor observados y estimación de biomasa/rinde solo con calibración.
- Erosión: diferencias de líneas de ribera y modelo sedimentológico.
- Riesgo agroclimático: calor, heladas, déficit hídrico, tormentas.

## Calidad y restricciones
- Nunca inferir superficie inundada a partir de altura hidrométrica sin modelo calibrado.
- No confundir observación satelital con pronóstico ni fotogramas interpolados con escenas reales.
- Controlar disponibilidad real por país, fechas, resolución, licencias y costos de API.
- Evitar URLs externas arbitrarias en servidor y revisar acceso a datos por credenciales.
- Los módulos y variables registradas no prueban que sus fuentes estén conectadas.
- Antes de producción: tests unitarios, integración backend, render Leaflet/MapLibre, reproyección, caché, control de fallos, validación de fuentes y `npm run build`.

## Siguiente entrega operativa
Conectar un adaptador de escenas reales verificadas y el panel al mapa principal; comenzar con series de agua y NDVI en cuencas compartidas del Paraná/Paraguay/Uruguay. Luego generalizar por cuenca y país, incorporando máscara geográfica y ejecución de modelos calibrados.
