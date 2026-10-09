# DOTS Campo · Registro internacional de fuentes reales

Verificación: 6 de octubre de 2026, Argentina. Las pruebas JSON llevan su hora UTC y URL exacta en `evidencia/`. Este registro distingue integración, prueba de catálogo y documentación: una página web no constituye una API conectada. No se afirma conexión a todas las APIs del mundo.

## Integraciones implementadas

| Fuente | Variables o productos | Acceso e implementación |
|---|---|---|
| Open-Meteo | 37 variables horarias y 12 diarias, 7 días | `/api/variables`, consulta real probada en Corrientes, Argentina. Datos de modelos, no sensores. [Documentación](https://open-meteo.com/en/docs) |
| NOAA GFS, ECMWF IFS, DWD ICON, ECCC GEM, JMA GSM, CMA GRAPES, Météo-France ARPEGE | Temperatura, humedad, precipitación y viento por modelo; 3 días | `/api/modelos` vía Open-Meteo; consulta real de siete modelos probada. No son siete conexiones directas a agencias ni un ensemble calibrado. |
| NASA POWER | Temperatura, humedad, precipitación diarias | `/api/historico`; 30 días recientes con rezago. [API](https://power.larc.nasa.gov/docs/services/api/) |
| ERA5 | Temperatura media y precipitación diaria; agregación anual | `/api/serie?years=20` o `30`, vía Open-Meteo. Reanálisis, no observación de estación. |
| GloFAS | Caudal diario modelado | `/api/rios`, vía Open-Meteo. Grilla/cuenca próxima, no aforo garantizado del arroyo del lote. |
| Earth Search / Sentinel-2 L2A | Escenas, fecha, nubosidad de escena y miniaturas RGB | `/api/escenas`, catálogo STAC implementado. No NDVI calculado ni imagen en vivo. [API](https://earth-search.aws.element84.com/v1/) |
| MPI-ESM1-2-XR / CMIP6 | Temperatura y precipitación 2031–2040 | `/api/proyeccion`, vía Open-Meteo. Proyección de un modelo, no pronóstico ni consenso multimodelo. |
| ISRIC SoilGrids | Nitrógeno total medio estimado a 0–5 cm | `/api/suelo` implementado; consulta anterior no respondió. Mantener «sin dato». No nitrógeno disponible ni medición actual. |

Los modelos globales permiten consultas por coordenadas en los países solicitados, incluidos Rusia y toda Europa. La cobertura del modelo no implica que haya estaciones, todos los productos satelitales o todas las variables disponibles en cada lugar. La prueba puntual no verifica todas las ubicaciones del planeta.

## Fuentes oficiales por país / región

| País / región | Fuente y referencia oficial | Qué se incorpora | Estado exacto en esta prueba |
|---|---|---|---|
| Brasil | [INMET WIS2 OGC API](https://wis2bra.inmet.gov.br/oapi/collections?f=json), [BDMEP](https://bdmep.inmet.gov.br/), [INPE TerraBrasilis](https://terrabrasilis.dpi.inpe.br/servicos-disponiveis/) | Estaciones SYNOP, históricos; cobertura vegetal y deforestación | Observaciones SYNOP directas conectadas en `/api/inmet`: muestra de hasta 50 registros en ±2 grados, últimos 30 días. Catálogo de 6 colecciones probado. BDMEP/TerraBrasilis aún no conectados. |
| Argentina | [SMN WIS2](https://w2b.smn.gov.ar/oapi/collections?f=json), [descarga SMN](https://ws2.smn.gob.ar/descarga-de-datos) | Estaciones automáticas y manuales, registros meteorológicos | Observaciones SYNOP manuales directas conectadas en `/api/smn`: muestra de hasta 50 registros en ±2 grados, últimos 30 días. Catálogo de 5 colecciones probado; no archivo histórico completo. |
| Chile | [DMC WIS2](https://wischile.meteochile.gob.cl/oapi/collections?f=json), [servicios climáticos](https://climatologia.meteochile.gob.cl/application/index/busqueda) | SYNOP, datos climáticos, estaciones y servicios JSON | Observaciones horarias WIS2 directas conectadas en `/api/dmc`: muestra de hasta 50 registros en ±2 grados, últimos 30 días. Catálogo de 6 colecciones probado. Otros servicios JSON DMC pueden requerir usuario/token. |
| Colombia | [IDEAM DHIME](https://ideam.gov.co/dhime) | Series meteorológicas e hidrológicas, descarga oficial | Portal documentado; API pública de extracción no verificada. Adaptador pendiente. |
| Venezuela | [INAMEH SYNOP en catálogo WIS2 de ECCC](https://wis2-gdc.weather.gc.ca/collections/wis2-discovery-metadata/items/urn%3Awmo%3Amd%3Ave-inameh%3Asinopticos?f=html) | Observaciones sinópticas publicadas por INAMEH | Metadatos oficiales localizados; descarga/decodificación aún no probada ni conectada. |
| México | [SMN/CONAGUA](https://smn.conagua.gob.mx/en/climatologia/informacion-climatologica/informacion-estadistica-climatologica) | Estadística histórica, temperatura y lluvia por estación | Descargas oficiales documentadas; API JSON estable no verificada ni conectada. |
| Estados Unidos | [NOAA CDO API](https://www.ncei.noaa.gov/cdo-web/webservices/v2), [USGS Water Data](https://api.waterdata.usgs.gov/) | Observaciones e históricos, caudales y niveles medidos | NWS observación de estación conectada directamente en `/api/nws`, probada en Kansas; cobertura estadounidense. CDO necesita token y USGS tiene límites: estos dos adaptadores siguen pendientes. GFS también consultado vía Open-Meteo. |
| Canadá | [ECCC GeoMet](https://eccc-msc.github.io/open-data/msc-geomet/readme_en/), [OGC API](https://api.weather.gc.ca/collections?f=json) | Datos meteorológicos e hidrológicos, series y cartografía según colección | Observaciones climáticas horarias directas conectadas en `/api/eccc`, con fecha, unidades y flags: muestra de 50 registros (hasta 250 valores). Catálogo de 104 colecciones probado. GEM también vía Open-Meteo. |
| Todos los países europeos | [Copernicus Data Space](https://dataspace.copernicus.eu/analyse/apis), [CDS](https://cds.climate.copernicus.eu/how-to-api) | Sentinel, ERA5, clima y productos de agua según colección | Cobertura continental mediante productos globales; no conexión individual a cada servicio nacional. Sentinel-2/ERA5 implementados mediante Earth Search/Open-Meteo. CDS y procesamiento Sentinel Hub directos requieren cuenta/credenciales y aceptación de condiciones. |
| Alemania / Francia y ECMWF europeo | [Modelos Open-Meteo](https://open-meteo.com/en/docs) | Pronósticos ICON, ARPEGE, IFS | Probados vía Open-Meteo. Otros servicios nacionales europeos deberán registrarse y validarse por separado. |
| Sudáfrica | [SAWS datos climáticos](https://www.weathersa.co.za/home/equiries_climatedata) | Registros oficiales meteorológicos y climáticos | Solicitud de datos documentada; API pública sin credenciales no verificada. No conectado. Modelos globales sí disponibles. |
| Japón | [JAXA G-Portal](https://www.gportal.jaxa.jp/), [acceso a productos](https://gportal.jaxa.jp/gpr/information/download), [JMA vía Open-Meteo](https://open-meteo.com/en/docs/jma-api) | Observación terrestre según misión y producto; pronóstico GSM | JMA GSM probado vía Open-Meteo. G-Portal documentado, sin descarga conectada; verificar cuenta y método del producto. |
| China | [CMA vía Open-Meteo](https://open-meteo.com/en/docs/cma-api), [NSMC Fengyun](https://data.nsmc.org.cn/DataPortal/en/home/index.html) | Pronóstico GRAPES; productos satelitales Fengyun | GRAPES probado vía Open-Meteo. Fengyun documentado; registro/formulario y cuotas según proveedor; no conectado. |
| Rusia | [Roshydromet datos abiertos](https://www.meteorf.gov.ru/opendata/), [Roscosmos](https://www.roscosmos.ru/) | Evaluar archivos hidrometeorológicos y observación terrestre por producto | Instituciones y fuentes oficiales verificadas documentalmente. No se verificó una API de observaciones accesible; no conectado. Datos abiertos administrativos no equivalen a series meteorológicas. Modelos globales cubren territorio ruso. |
| India (ampliación) | [ISRO/NRSC Bhuvan](https://www.nrsc.gov.in/nrscnew/Services_Bhuvan_overview.php) | Productos de observación terrestre y servicios geoespaciales | Documentado; no conectado. Producto, área, método y condiciones por verificar. |
| Starlink | [API de telemetría](https://starlink.com/ml/support/article/90109cc2-c7ec-31ff-d160-0a87f16ef759) | Rendimiento y estado de terminales; conectividad rural | Acceso empresarial indicado por Starlink. No credenciales ni conector activo. No ofrece en este servicio temperatura del campo, NDVI o nitrógeno. |

## Variables disponibles y previstas

**Ya consultadas:** temperatura 2 m, humedad relativa, punto de rocío, sensación térmica, probabilidad de precipitación, precipitación total, lluvia, chaparrones, nieve, espesor de nieve, presión al nivel del mar y de superficie, nubes totales/bajas/medias/altas, visibilidad, evapotranspiración, ET0, déficit de presión de vapor, viento/dirección/ráfagas a 10 m, temperatura de suelo a 0/6/18/54 cm, humedad de suelo a 0–1/1–3/3–9/9–27/27–81 cm, radiación corta/directa/difusa/normal directa/terrestre. Resolución horaria y unidades devueltas por la fuente, 7 días. Valores modelados.

**12 campos diarios:** máxima/mínima de temperatura, precipitación acumulada, ET0, UV máximo, probabilidad máxima de precipitación, viento/ráfagas máximas, radiación acumulada, duración de insolación, amanecer y atardecer. Son campos/estadísticas de esas variables, no 12 fenómenos adicionales independientes.

**Derivada en el frontend:** THI desde temperatura/humedad. Indicador sin clasificación veterinaria automática.

**Pendientes, sin valores simulados:** NDVI/EVI/NDMI/LAI; biomasa y proteína del pasto (requieren calibración local); temperatura superficial satelital; SMAP; precipitación GPM; incendios FIRMS; inundación Sentinel-1; niveles de ríos medidos; nitrógeno disponible y laboratorio; inventario, ubicación, peso y salud animal; agua de bebederos y estaciones IoT. No prometer estimación precisa de nitrógeno/forraje/salud desde una sola imagen.

## Contrato de cada medición en producción

Registrar variable, valor o null, unidad, tipo (observación/modelo/reanálisis/proyección/derivada), organismo originador, intermediario, producto/modelo/versión, coordenadas y geometría de grilla/estación, resolución espacial y temporal, profundidad/altura, hora del dato, hora de consulta, calidad, incertidumbre disponible, licencia y enlace original. La prueba actual guarda JSON original, unidades, coordenadas y fecha de consulta; aún no normaliza todo este contrato ni tiene base histórica persistente.

Adaptador → control de unidades/calidad/tiempos → archivo original + PostGIS/series temporales → API del módulo → mapa y gráficos. Conservar el origen y no mezclar modelos como si fueran mediciones. Las cargas de décadas y procesamiento raster se ejecutarán en trabajos de fondo con caché, no en cada apertura del dashboard.

Si una fuente falla: «sin dato», conservar fecha del último dato verificable cuando exista, nunca reemplazar con un número inventado. Comprobar licencia y cuota antes de uso comercial; acceso gratuito de prueba no garantiza condiciones comerciales gratuitas.

## Conexión directa adicional y publicación

`/api/metnorway` conecta directamente a MET Norway Locationforecast: pronóstico para Corrientes probado, 93 tiempos recibidos. Se conservan unidades, fechas y atribución; caché en memoria hasta Expires, compresión gzip e identificación configurable mediante `DOTS_CONTACT_URL`. Caché por instancia, no compartida entre todas las funciones.

Los seis adaptadores directos se probaron sin clave ni pago. Las condiciones del proveedor y la licencia de cada producto siguen vigentes; no significa gratuidad ilimitada para cualquier modalidad comercial. Ver `PUBLICAR-GITHUB-VERCEL.md` para publicación y costos. Las muestras de estaciones no garantizan cobertura de un lote ni una serie histórica completa.
