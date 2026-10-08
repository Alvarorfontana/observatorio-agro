# DOTS Campo v1.8 — Adopción de la programación y correcciones

Esta versión adopta como regla ejecutable que **API REST, STAC, WMS/WMTS, WFS, descarga raster y plataforma de procesamiento no son equivalentes**.

## Corrección funcional crítica
En versiones anteriores `changeView()` reutilizaba `sources[key]` si la fuente ya había sido consultada. Al cambiar de lote/polígono, un botón podía mostrar el resultado espacial anterior. v1.8 fuerza una nueva consulta al pulsar el botón, enviando el polígono actual.

## Registro de plataformas
`GET /api/fuentes/plataformas` devuelve el protocolo, acceso, capacidad y estado de cada integración. No convierte una fuente registrada en una fuente operativa.

Se distinguen: NASA POWER/REST; NASA GIBS/WMS-WMTS; Sentinel-2 Earth Search/STAC; Copernicus Data Space/STAC; Landsat Planetary Computer/STAC; CNES/DLR/Digital Earth Africa/STAC; INTA Suelos/WMS; Sentinel Hub/OAuth + Processing/Statistical API; Google Earth Engine/OAuth/Cloud; CONAE-SAOCOM como fuente prioritaria no certificada hasta probar un producto/servicio oficial concreto.

## Regla de aceptación
BOTÓN → ADAPTADOR → SERVICIO REAL → RESPUESTA VÁLIDA → POLÍGONO → PROCESAMIENTO → VISUALIZACIÓN → GRÁFICO/INFORME, según la capacidad de la fuente.

Catálogo != imagen. Imagen != estadística raster. Credencial presente != integración certificada.
