# Conexiones para investigación · Observatorio Agro

Actualización: 7 de octubre de 2026 UTC. Son **20 servicios/productos seleccionados**, no veinte agencias independientes conectadas. Los ocho primeros tienen adaptadores públicos consultados realmente; cuatro devuelven valores, cuatro catálogos. FIRMS tiene adaptador pero falta clave. Los once restantes requieren desarrollo o activación. Los límites, cobertura y licencias se revisan antes de uso intensivo.

| # | Servicio | Variables / utilidad | Acceso y estado real |
|---|---|---|---|
| 1 | [CAMS vía Open-Meteo](https://open-meteo.com/en/docs/air-quality-api) | PM2.5, PM10, CO, NO₂, SO₂, ozono, polvo, aerosoles, UV, amoníaco | Adaptador probado sin clave; 9 series válidas en Corrientes, amoníaco sin datos. Modelo en grilla. |
| 2 | [Elevación Open-Meteo](https://open-meteo.com/en/docs/elevation-api) | Elevación DEM | Adaptador probado sin clave; estimación de terreno, no sensor. |
| 3 | [INA Argentina](https://alerta.ina.gob.ar/pub/gui/datos) | Altura del Paraná, altura mensual histórica, series meteorológicas | Adaptador probado sin clave. Bella Vista serie 22: 30 registros; serie 25500: 359 registros mensuales en ventana de 30 años; temperatura 37299: 266 registros. |
| 4 | [USGS Water Data](https://api.waterdata.usgs.gov/ogcapi/v1/) | Datos diarios de agua, caudal/nivel/calidad según estación y código | Adaptador probado, estación USGS-06887000 devolvió 50 registros. Cuotas públicas; fuera de EE.UU. puede devolver cero registros. |
| 5 | [NASA CMR](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html) | Descubrimiento MOD13Q1, MOD11A2, MOD16A2GF, MCD15A3H | Catálogo probado sin clave: fechas y granules. No calcula NDVI ni extrae píxeles. |
| 6 | [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/api/) | Catálogo y extracción de productos de vegetación, temperatura y ET | Catálogo público probado: 187 productos. Extracción no conectada; requiere Earthdata y trabajo asíncrono. |
| 7 | [Planetary Computer STAC](https://planetarycomputer.microsoft.com/docs/quickstarts/reading-stac/) | Landsat Collection 2 Level 2 | Catálogo probado: 3 escenas en el punto. Lectura y estadísticas raster pendientes; SAS según recurso. |
| 8 | [Copernicus Data Space STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html) | Sentinel-1 GRD radar | Catálogo probado: 3 escenas. Procesamiento/calibración radar y extracción pendientes. |
| 9 | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/) | Detecciones térmicas VIIRS NRT | Adaptador preparado; no se consultó con credencial. MAP_KEY gratuita con correo/aceptación. |
| 10 | [FAO WaPOR v3](https://www.fao.org/in-action/remote-sensing-for-water-productivity/en) | ET real y de referencia, productividad primaria, agua | API v3 pública sin clave; conexión y extracción pendientes. Cobertura/resolución por producto. |
| 11 | [UCSB CHIRPS](https://www.chc.ucsb.edu/data/chirps3) | Precipitación histórica desde 1981 | Archivos públicos; extracción raster pendiente. No es una API puntual equivalente a Open-Meteo. |
| 12 | [Copernicus CDS](https://cds.climate.copernicus.eu/how-to-api) | ERA5/ERA5-Land, suelo, clima histórico | Cuenta, token y aceptación por dataset; cliente/colas pendientes. ERA5 ya se consulta vía Open-Meteo. |
| 13 | [Copernicus ADS](https://ads.atmosphere.copernicus.eu/how-to-api) | Composición atmosférica CAMS | Cuenta y token; descargas directas pendientes. CAMS ya está vía Open-Meteo. |
| 14 | [Sentinel Hub Processing](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview.html) | NDVI, imágenes y estadísticas por polígono | OAuth CDSE, cupos y procesamiento pendientes. No se creó cuenta ni client secret. |
| 15 | [Google Earth Engine](https://developers.google.com/earth-engine/guides/access) | Procesamiento de múltiples archivos históricos | Google Cloud project y verificación de uso no comercial. No conectado; otras funciones Cloud pueden generar costos. |
| 16 | [NOAA CDO](https://www.ncei.noaa.gov/cdo-web/webservices/v2) | Estaciones y series climáticas históricas | Token solicitado con correo; conector pendiente. NOAA NWS ya tiene conector independiente. |
| 17 | [ANA HidroWeb](https://www.snirh.gov.br/hidroweb/) | Hidrología de Brasil | API requiere solicitud a ANA; acceso no solicitado ni recibido. No se enviaron correos. |
| 18 | [INPE Queimadas](https://data.inpe.br/queimadas/) | Focos térmicos y archivos de incendios | Datos públicos; adaptación y controles de unidades/fechas pendientes. |
| 19 | [INPE TerraBrasilis](https://terrabrasilis.dpi.inpe.br/) | Deforestación, alertas y uso del suelo | Catálogos/servicios geoespaciales públicos; conector pendiente. |
| 20 | [JAXA G-Portal](https://gportal.jaxa.jp/gpr/) | Productos satelitales japoneses | Registro/licencia según producto; selección y descarga pendientes. |

## Conectores anteriores conservados

Clima: Open-Meteo (37 variables horarias y 12 diarias solicitadas, más 4 actuales), comparación GFS/IFS/ICON/GEM/JMA/CMA/ARPEGE, NASA POWER, GloFAS, ERA5 20–30 años, proyección MPI-ESM1-2-XR. Satélite: Earth Search Sentinel-2. Estaciones directas: SMN Argentina, INMET Brasil, DMC Chile, ECCC Canadá, NWS EE.UU., MET Norway. SoilGrids tiene consulta preparada; cuando no responde se muestra Sin dato. No se promete disponibilidad permanente.

## Activación

1. Probar las fuentes sin cuenta desde el panel. `GET /api/fuentes/estado` muestra adaptadores y FIRMS.
2. Para FIRMS solicitar la clave en el enlace oficial y cargar `FIRMS_MAP_KEY` en Vercel > Settings > Environment Variables. Nunca `VITE_FIRMS_MAP_KEY`, ni subir claves al repositorio. Volver a desplegar y probar la consulta. Cero detecciones sólo corresponde a una respuesta válida y al área/período indicados.
3. Earthdata, CDS, ADS, CDSE y Google requieren cuentas reales y aceptación de condiciones. Las cuentas no se han creado. Sus integraciones no se activan por simplemente guardar una clave: todavía necesitan desarrollo, colas y validación.
4. Rutas ejemplo: `/api/fuentes/ina?series=22&days=30`, `/api/fuentes/ina?series=25500&years=30`, `/api/fuentes/ina?series=37299&days=2`, `/api/fuentes/usgs?site=USGS-06887000`, `/api/fuentes/informe?lat=-28.507&lon=-59.043&inaSeries=22`.

## Límites científicos

NO₂ y NH₃ del aire no son nitrógeno disponible del suelo. SoilGrids representa estimaciones edafológicas, no análisis de laboratorio del potrero. NDVI no mide animales ni garantiza calidad nutricional. Caudal modelado no es nivel observado. Estaciones a distancia no son sensores del lote. Starlink aporta conectividad y telemetría de terminales, no imágenes meteorológicas/NDVI; no se agregó como fuente ambiental. Rusia, China y los demás países del catálogo mundial no están todos conectados directamente.
