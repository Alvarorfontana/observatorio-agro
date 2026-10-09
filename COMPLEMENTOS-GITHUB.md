# DOTS Campo v1.9 — Complementos de GitHub para el modelo

Objetivo: pasar de **catálogo** a **análisis raster por lote** manteniendo la función de Vercel liviana.

Límites vigentes (docs de Vercel, sept. 2026): funciones Python hasta 500 MB descomprimidas (5 GB en beta "large functions"), duración máx. 300 s en Hobby y 800 s en Pro, memoria 2 GB en Hobby. Hobby es sólo para uso no comercial.

## Medición de tamaño (Python 3.13, instalación limpia)

| Paquete | Peso aprox. | ¿Entra en Vercel? |
|---|---|---|
| rasterio + numpy (GDAL incluido) | ~200 MB | Sí entra (límite Python 500 MB), pero arranques en frío más lentos |
| earthengine-api (+ google-api-python-client) | ~150 MB extra | Junto con rasterio queda cerca del límite |
| google-auth (sólo token OAuth) | ~2 MB | Sí |

Conclusión: igual conviene delegar el raster pesado a servicios que ya ejecutan esas librerías (respuesta más rápida, menos memoria). DOTS envía el polígono y recibe estadísticas o una imagen recortada. Si hiciera falta rasterio local, ahora es posible en Vercel.

## Mapa de repositorios → fuente → cómo se usa en DOTS

| Repo GitHub | Qué resuelve | Uso en DOTS v1.9 | Credencial |
|---|---|---|---|
| [developmentseed/titiler](https://github.com/developmentseed/titiler) + [cogeotiff/rio-tiler](https://github.com/cogeotiff/rio-tiler) | Estadística zonal y recorte de COG por polígono | Vía **Planetary Computer Data API** (instancia pública de TiTiler-PgSTAC): NDVI Sentinel-2 por lote, máscara de nubes SCL dentro del lote, PNG recortado | No |
| [stac-utils/pystac-client](https://github.com/stac-utils/pystac-client) | Búsqueda STAC | Se replica con `requests` (ya existía `_stac`); ahora busca por `intersects` del polígono real | No |
| [sentinel-hub/sentinelhub-py](https://github.com/sentinel-hub/sentinelhub-py) | Statistical API | Llamada REST directa a CDSE Sentinel Hub con OAuth2 client credentials | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` |
| [Open-EO/openeo-python-client](https://github.com/Open-EO/openeo-python-client) | Procesamiento en la nube openEO | Grafo de procesos JSON enviado por REST a `openeo.dataspace.copernicus.eu` (`/result` síncrono) | mismas CDSE |
| [google/earthengine-api](https://github.com/google/earthengine-api) | Series largas MODIS/Landsat | Expresión serializada enviada a la REST API `value:compute`; token con `google-auth` | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS_JSON` |

## Relevamiento ampliado (octubre 2026)

### Variables de clima
| Repo | Qué hace | Encaje DOTS |
|---|---|---|
| [ajwdewit/agera5tools](https://github.com/ajwdewit/agera5tools) | AgERA5 (ERA5 adaptado a agricultura, Copernicus CDS): espejo local, recorte, series por punto y servidor JSON. MIT, activo | Servicio aparte (no Vercel) que DOTS consulta por HTTP; necesita `CDS_API_KEY` |
| [eWaterCycle/era5cli](https://pypi.org/p/era5cli) | Descarga ERA5 por línea de comandos | Útil para un worker programado, no para la función web |
| Open-Meteo (ya integrado) | ERA5 / ERA5-Land por REST | Sigue siendo la vía liviana para series en Vercel |

### Satélites meteorológicos
| Repo | Qué hace | Encaje DOTS |
|---|---|---|
| [blaylockbk/goes2go](https://github.com/blaylockbk/goes2go) | GOES-East/West desde el archivo NOAA en AWS, compuestos RGB. MIT, activo | GOES-East cubre Argentina; worker externo para nubosidad/temperatura de tope |
| [joaohenry23/GOES](https://github.com/joaohenry23/GOES) | Descarga y manejo GOES-16 a 19. BSD-3 | Alternativa a goes2go, mantenido desde Sudamérica |
| [pytroll/satpy](https://github.com/pytroll/satpy) | Lectura y compuestos de GOES, Meteosat, Himawari, VIIRS | Estándar para procesar; pesado para Vercel |
| NASA GIBS (ya integrado) | Teselas WMTS listas de GOES-East | Vía liviana para mostrar en el mapa sin procesar |

### Delimitación de lotes
| Repo | Qué hace | Encaje DOTS |
|---|---|---|
| [fieldsoftheworld/ftw-baselines](https://github.com/fieldsoftheworld/ftw-baselines) | Benchmark + CLI `ftw inference` con modelos preentrenados (incluye Delineate Anything). MIT | Worker con GPU/CPU que devuelve polígonos vectoriales sugeridos |
| Mapa global FTW en [source.coop/ftw/global-data](https://source.coop/ftw/global-data) | 3170 millones de polígonos 2024-2025 a 10 m, GeoParquet fiboa, CC-BY | Sugerir lotes existentes alrededor de un punto. Ojo: sólo cultivos anuales, no pasturas; Argentina procesada pero no validada |
| [Lavreniuk/Delineate-Anything](https://github.com/Lavreniuk/Delineate-Anything) | Segmentación de parcelas YOLOv11, 0,25 a 10 m, muy rápido | Mejor modelo actual para delimitación desde imagen |
| [sentinel-hub/field-delineation](https://github.com/sentinel-hub/field-delineation) | ResUnet-a sobre Sentinel-2. MIT | Archivado desde 2023, sólo como referencia |

La delimitación con modelos (FTW, Delineate Anything) necesita GPU o procesos largos: va en un **worker DOTS** separado (Render o Google Cloud Run) que la API de Vercel llama por HTTP. La lectura del mapa global FTW (GeoParquet con duckdb) y AgERA5 sí podrían entrar en una función Python de Vercel. Queda como siguiente etapa.

## Endpoints nuevos

| Ruta | Capacidad | Estado inicial |
|---|---|---|
| `GET /api/fuentes/ndvi?lat&lon&polygon` | ANALYSIS: NDVI por escena (media, mediana, p2/p98, % píxeles despejados en el lote) | Abierta · validar en Vercel |
| `GET /api/fuentes/ndvi-imagen?item&polygon` | IMAGE: PNG NDVI recortado al lote + bounds para el mapa | Abierta · validar en Vercel |
| `GET /api/fuentes/sentinel-hub-ndvi` | ANALYSIS: serie NDVI zonal con máscara de nubes (Statistical API) | REQUIRES_CREDENTIAL |
| `GET /api/fuentes/openeo-ndvi` | ANALYSIS: serie NDVI zonal por openEO | REQUIRES_CREDENTIAL |
| `GET /api/fuentes/gee-ndvi` | ANALYSIS: serie MODIS MOD13Q1 (250 m, 16 días) hasta 20 años | REQUIRES_CREDENTIAL |

Todas exigen polígono: sin lote dibujado devuelven 400. No hay promedio zonal sobre un punto.

## Capas abiertas NASA GIBS en el mapa (sin backend)

Selector "Capas NASA" en la barra del mapa, WMS EPSG:3857 sin clave y sin `TIME` (GIBS entrega la última fecha disponible):

| Capa GIBS | Qué muestra | Escala |
|---|---|---|
| `MODIS_Terra_NDVI_8Day` | NDVI regional | 250 m |
| `MODIS_Terra_Land_Surface_Temp_Day` | Temperatura de superficie diurna | 1 km |
| `SMAP_L4_Analyzed_Surface_Soil_Moisture` | Humedad de suelo 0–5 cm (modelo asimilado) | 9 km |
| `IMERG_Precipitation_Rate` | Tasa de lluvia GPM | ~10 km |

Son imagen (capacidad IMAGE), no estadística del lote. Los identificadores se tomaron del catálogo GIBS y deben confirmarse en el despliegue: si una capa no carga, el mapa avisa y no muestra nada inventado.

## Reglas que se mantienen

- Escena con menos de 60 % de píxeles despejados **dentro del lote** se informa como `nublada`, no se usa para la serie ni para interpretar.
- Sentinel-2 baseline ≥ 04.00 trae offset de reflectancia −1000: la fórmula NDVI lo corrige (`(B08-B04)/(B08+B04-2000)`).
- Credencial presente ≠ fuente certificada. Las tres fuentes protegidas quedan `sin validar end-to-end` hasta una consulta real exitosa en Vercel.
- La imagen NDVI es de 10 m; un lote chico puede tener pocos píxeles y se informa el conteo.

## Cómo validar en el despliegue

```
python scripts/validate_sources.py > source-audit.json
```
o desde la interfaz: dibujar un lote → botón Vegetación.

## Delimitación automática gratuita (v2.1)

Botón **Automático · FTW** en Operaciones del lote. Lee en el navegador el mapa global de lotes 2025 de Fields of the World:

- Archivo: `https://data.source.coop/ftw/global-field-boundaries/pmtiles/ftw-global-fields-2025.pmtiles`, capa `fields`, zoom 9–13 (sin simplificar en z13). Propiedades: `confidence` (0–100) y `metrics:area` (m²).
- Se pide por rangos HTTP a través del reenvío `/ftw/*` de `vercel.json` (mismo dominio, sin CORS). En desarrollo lo hace el proxy de Vite; `FTW_PROXY_TARGET` permite apuntar a un archivo de prueba.
- Al tocar dentro de un contorno se reconstruye el lote uniendo las partes de las teselas vecinas (`polygon-clipping`), se simplifica a menos de 500 vértices y se guarda como cualquier lote dibujado.
- Verde: confianza ≥ 69 (umbral recomendado por FTW). Ámbar: revisar el borde.
- Sin servidor propio, sin clave, sin costo. Licencia de datos CC-BY-4.0: la atribución se muestra en pantalla.
- Límite: FTW mapea cultivos anuales; en pasturas puede no haber contorno. Ahí sigue el dibujo manual.

Librerías nuevas en el frontend: `pmtiles` (BSD-3), `@mapbox/vector-tile` (BSD-3), `pbf` (BSD-3), `polygon-clipping` (MIT).
