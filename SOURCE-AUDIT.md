# DOTS Campo — criterio de certificación de fuentes

Una fuente no se declara operativa por tener botón, URL o credencial. La certificación es por capacidad:

- **IMAGE**: devuelve una imagen/raster que el mapa puede representar.
- **CATALOG**: encuentra productos/escenas; no equivale a imagen procesada.
- **MARKERS**: devuelve observaciones georreferenciadas que se representan como puntos.
- **ANALYSIS**: devuelve variables con fecha, unidad, procedencia y alcance.
- **REQUIRES_CREDENTIAL**: no se habilita como operativa.

Cadena objetivo: `polígono → fuente → producto → dato/raster → capa/marca → cálculo → gráfico → interpretación → PDF`.

## Estado de esta entrega

- NASA GIBS/MODIS: capa de imagen implementada; el PDF intenta obtener la misma familia de imagen WMS y superpone lote + marcas. Si GIBS falla, el informe lo declara.
- NASA FIRMS: consulta bbox derivado del polígono (+ margen), conserva coordenadas, fecha/sensor/FRP/confianza y marca si la detección cae dentro del lote. Requiere `FIRMS_MAP_KEY`.
- NASA POWER/Open-Meteo: variables y series; son grilla/punto representativo, no se rotulan como promedio zonal.
- Sentinel-2: catálogo intersectando la envolvente del lote. No se rotula como NDVI ni raster procesado.
- Sentinel-1/Landsat y conectores protegidos: catálogo/credencial según corresponda; no aparecen como capa de imagen operativa en la barra principal.
- SoilGrids: consulta puntual/modelada. No se presenta como análisis de laboratorio ni promedio zonal.
- CONAE/SAOCOM: documentado como fuente prioritaria, pero los productos de archivo SAOCOM requieren registro/licencia. No se presenta falsamente como raster operativo sin ese acceso.

Ejecutar `python scripts/validate_sources.py > source-audit.json` en un entorno con Internet y las variables de Vercel para obtener auditoría real de ese despliegue.
