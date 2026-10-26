# DOTS Campo — evolución interactiva de inundaciones (diseño de integración)

## Dos modos separados
1. **Observado**: secuencia temporal de máscaras reales de agua de Copernicus GFM / Sentinel-1; fechas y resolución de cada pasada visibles. Distinguir agua permanente de inundación detectada; marcar ausencia de observación, nubosidad (si se usan imágenes ópticas), incertidumbre y huecos temporales. No interpolar máscaras como si fueran observaciones.
2. **Escenario hipotético**: topografía + cotas en referencia vertical común + condiciones hidrológicas; no extrapolar el nivel de una estación a toda la llanura. Sin modelo hidráulico calibrado, rotular explícitamente como ilustrativo.

## Fuentes y accesos
- GFM: https://global-flood.emergency.copernicus.eu/ ; documentación https://extwiki.eodc.eu/GFM/PUM
- INA SIyAH: https://alerta.ina.gov.ar/ y asistente API https://alerta.ina.gov.ar/pub/gui/datos
- INA pronóstico de niveles Paraná: recurso `siyah:tabprono_parana` (7 y 14 días según producto).
- Sentinel-1: catálogo/radar ya existente en `gfm.py` y `radar.py`. Reusar, no duplicar.
- Elevación JAXA ALOS / otros DEM: validar licencia, referencia vertical y error.

## Interfaz prevista
Mapa base + máscara azul con leyenda; línea de tiempo por fecha de adquisición con reproducir/pausar, velocidad, comparación antes/después; gráfico hidrométrico INA sincronizado; selector de estación; área inundada (ha/km²) calculada sobre píxeles válidos; botón de informe PDF y descarga GeoJSON/GeoTIFF cuando la licencia lo permita.

## Orden de implementación
1. Verificar con datos reales `gfm.py` y `radar.py`, fechas y georreferenciación para Corrientes / Bella Vista.
2. Consultar metadatos y series INA mediante su API; documentar estación, cero de escala, datum y unidades.
3. Generar máscaras observadas y geometrías simplificadas con fechas; no inventar fotogramas entre pasadas.
4. Añadir control temporal al frontend y pruebas de reproducción sobre datos reales.
5. Informes PDF, avisos y eventualmente escenarios hidráulicos calibrados.

## Criterio de publicación
Sin validación end-to-end no declarar operativa una capa. Mostrar estado sin datos cuando corresponda. El módulo no sustituye alertas oficiales de protección civil.
