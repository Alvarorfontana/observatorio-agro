# DOTS v2.2 · Crecidas y focos de calor de NASA GIBS

Tomado de NASA Worldview (repo nasa-gibs/worldview): las capas del producto global de crecidas y de anomalías térmicas, servidas por GIBS sin clave.

## Qué se sumó

- **Mapa del lote** (selector de capas NASA): `MODIS_Combined_Flood_3-Day`, `VIIRS_Combined_Flood_3-Day` y `VIIRS_NOAA20_Thermal_Anomalies_375m_All`, con leyenda de crecidas. Estas capas sólo existen en EPSG:4326, así que el WMS se pide en ese sistema.
- **Panel Cuenca del Plata**: nueva imagen "Agua detectada por satélite · 3 días" sobre la zona en alerta (MODIS, con VIIRS de respaldo), con leyenda.
- **Informe PDF de la cuenca**: la misma imagen entra en "Imágenes de la zona". Si la capa de crecidas no responde, se omite (la foto del día ya está aparte).

## Lectura de colores

Celeste: agua habitual · amarillo: anegamiento recurrente (desde la versión 1.1 del producto, dic. 2025) · rojo: agua fuera de lo habitual · gris: sin dato por nubes o relieve.

## Límites

Resolución ~250 m: es escala regional, no de lote. Las sombras de nubes pueden dar falsas detecciones; confirmar con la imagen del día. Para el informe por localidad sigue mandando Copernicus GFM (radar Sentinel-1), que ve a través de las nubes.

Fuente: NASA LANCE MCDWD/VCDWD vía GIBS · uso libre citando a NASA.
