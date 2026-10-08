# DOTS Campo v0.9 — cierre funcional

## Decisiones cerradas
- Un solo Informe Territorial DOTS. `/api/fuentes/analizar` y `/api/fuentes/agentic/pdf` producen el mismo formato.
- El informe recibe el polígono y calcula superficie y perímetro; incluye esquema del límite, métricas, rangos/referencias, gráfico lluvia–ET0, hallazgos, ENSO, agua, recomendaciones, límites y trazabilidad.
- Delimitación: triángulo, rectángulo y polígono libre, con validación de vértices y cruces.
- El análisis Agentic recibe el polígono y conserva la geometría en el resultado.
- Satélites/catálogos: Sentinel-2 y radar/Landsat ya expuestos; FIRMS usa clave de entorno; las fuentes que no responden se muestran como faltantes, nunca se inventan.

## Fuentes oficiales verificadas 07-10-2026
- Copernicus Data Space STAC: Sentinel-1 GRD/SLC y Sentinel-2 L1C/L2A, búsqueda espacial/temporal y filtros.
- NASA FIRMS: MODIS, VIIRS S-NPP/NOAA-20/NOAA-21 y productos disponibles según región; requiere MAP_KEY gratuita.
- CONAE: geoservicios OGC WMS/WFS disponibles públicamente; productos específicos pueden tener condiciones propias.
- IRI/Columbia: recursos ENSO y pronósticos estacionales disponibles; se usa como fuente climática de contexto, no como pronóstico puntual del lote.

## Regla de evidencia
Toda salida debe rotularse como observado, modelado, calculado/derivado, pronosticado o interpretación DOTS. No se presenta una inferencia como medición.

## Validación de despliegue
Python se valida con `python -m py_compile`. El build frontend requiere `npm ci && npm run build` en un entorno con acceso completo al registro npm.
