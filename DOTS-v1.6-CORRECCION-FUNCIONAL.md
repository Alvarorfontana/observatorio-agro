# DOTS v1.6 — Corrección funcional

- La barra satelital ya no llama “imagen” a catálogos: Sentinel-1/2 y Copernicus se presentan como búsqueda/catálogo hasta contar con raster procesado.
- NASA GIBS MODIS sigue como capa raster real visible.
- NASA FIRMS carga detecciones reales y las convierte en marcas geográficas automáticas cuando FIRMS_MAP_KEY responde.
- Los marcadores manuales se colocan haciendo clic en el mapa, no en el centro: agua/bebedero, ganado, temperatura/THI, vegetación/anomalía, observación e incendio.
- Las marcas se envían al análisis y al PDF; el esquema del polígono en PDF las representa.
- Botones operativos visibles: mapa base, NASA GIBS MODIS, FIRMS, NASA POWER, ENSO, SoilGrids; Sentinel-1/2 y Copernicus quedan correctamente rotulados como catálogo/búsqueda.
