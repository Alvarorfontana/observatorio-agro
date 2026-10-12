# DOTS Campo v1.9 — Relieve, línea de tiempo NDVI e importación de lotes

Ideas tomadas de GeoLibre (opengeos/GeoLibre, licencia MIT): procesamiento geoespacial en el navegador, lectura de COG por rangos HTTP, Time Slider y apertura directa de archivos vectoriales. El código es propio; no se copió código de GeoLibre.

## 1. Relieve y anegamiento del lote (nuevo)
- Fuente: Copernicus DEM GLO-30 (AWS Open Data), leído como COG con `geotiff.js` a través del rewrite `/dem` (Vercel y Vite). Sin clave, sin servidor de cálculo.
- Cálculo en el navegador (`src/dashboard/terrainCore.ts`): priority-flood (Barnes 2014), dirección D8, acumulación de flujo, pendiente de Horn e índice topográfico de humedad ln(a/tan β).
- Se analiza el lote con un margen de 0,8–5 km: el agua que llega al lote viene de afuera.
- Resultados: posición en el paisaje (bajo, media loma, loma), desnivel, pendiente, bajos cerrados ≥ 10 cm (ha, %, volumen), vías de escurrimiento (> 10 ha aguas arriba) y propensión a anegarse en 3 clases.
- Capas sobre el mapa: anegamiento, relieve sombreado, pendiente y humedad topográfica.
- Límite declarado: el DEM es de superficie (montes y construcciones suman altura). Es un indicador relativo, no una cota de inundación.

## 2. Línea de tiempo NDVI
Deslizador y reproducción sobre las escenas Sentinel-2 válidas del lote; la capa NDVI o color real cambia con la fecha.

## 3. Importar y exportar lotes
- Importar KML (Google Earth) o GeoJSON: cada polígono se guarda como lote con su nombre.
- Descargar todos los lotes en KML o GeoJSON.

## Criterio de verdad
Fuente → DEM → fecha de producto → polígono → variable → unidad → método → límite. Si el DEM no responde, el panel lo declara y no se sustituye por otro valor.
