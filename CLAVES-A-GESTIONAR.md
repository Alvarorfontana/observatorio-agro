# DOTS — Credenciales a gestionar

No compartir contraseñas por chat. Cargar secretos directamente en Vercel.

## Prioridad 1
- Copernicus Sentinel Hub: `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`
- Copernicus CDS / ERA5: `CDS_API_KEY`
- NOAA CDO: `NOAA_CDO_TOKEN`
- USGS M2M: `USGS_USERNAME`, `USGS_TOKEN`
- NASA Earthdata: `EARTHDATA_TOKEN`
- Copernicus Marine: `COPERNICUS_MARINE_USERNAME`, `COPERNICUS_MARINE_PASSWORD`
- Google Earth Engine: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`

## Prioridad 2
- OpenAQ v3: `OPENAQ_API_KEY`
- Global Forest Watch: `GFW_API_KEY`
- AEMET OpenData: `AEMET_API_KEY`
- EUMETSAT: `EUMETSAT_CONSUMER_KEY`, `EUMETSAT_CONSUMER_SECRET`
- JAXA G-Portal: `JAXA_USERNAME`, `JAXA_PASSWORD`
- ISRO MOSDAC: `MOSDAC_USERNAME`, `MOSDAC_PASSWORD`
- KMA: `KMA_AUTH_KEY`
- FengYun/CMA: `FENGYUN_USERNAME`, `FENGYUN_PASSWORD`

## Cómo obtener las tres que activan el NDVI avanzado (v1.9)

Las cuentas son personales: las crea el titular, no se pueden registrar desde DOTS.

**Copernicus Data Space** (activa Sentinel Hub y openEO, gratis)
1. Crear cuenta en https://dataspace.copernicus.eu
2. Entrar a https://shapps.dataspace.copernicus.eu/dashboard → User settings → OAuth clients → Create
3. Copiar Client ID y Client Secret (el secret se muestra una sola vez)
4. Vercel → Settings → Environment Variables: `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`

**Google Earth Engine** (serie MODIS 20 años, gratis para uso no comercial)
1. Crear proyecto en https://console.cloud.google.com y registrarlo en https://code.earthengine.google.com/register (uso no comercial)
2. Habilitar la Earth Engine API en el proyecto
3. IAM → Cuentas de servicio → Crear → rol "Earth Engine Resource Viewer" → Claves → JSON
4. Vercel: `GOOGLE_CLOUD_PROJECT` = id del proyecto, `GOOGLE_APPLICATION_CREDENTIALS_JSON` = contenido completo del JSON

Nota sobre la lista externa recibida: Sentinel Hub ya no se gestiona en sentinel-hub.com para el acceso gratuito sino en Copernicus Data Space; OpenAQ v3 sí exige API key; la URL de catálogo CONAE de esa lista no es oficial (usar https://catalogos.conae.gov.ar).

## Ya configurada previamente
- NASA FIRMS: `FIRMS_MAP_KEY`

Los botones protegidos están programados para informar `requiere credencial` hasta que Vercel tenga las variables. Tener la variable configurada no equivale todavía a certificar el dato: la fuente pasa a OPERATIVA sólo después de una consulta real válida.

## Alternativas gratuitas y sin clave (ya funcionando)

Mientras no estén las claves, DOTS obtiene las mismas variables de fuentes abiertas. Las claves suman resolución o historia, no son imprescindibles.

| Variable | Fuente con clave | Alternativa sin clave en uso | Respaldo automático |
|---|---|---|---|
| NDVI, EVI, SAVI, NDMI, NDWI por lote (10 m) | Copernicus Sentinel Hub / openEO | Microsoft Planetary Computer (Sentinel-2 L2A) | NASA ORNL DAAC · MODIS MOD13Q1 250 m |
| Color real del lote | Copernicus | Planetary Computer (Sentinel-2 TCI) | — |
| Serie larga de NDVI (20 años) | Google Earth Engine | NASA ORNL DAAC · MODIS (desde 2000) | — |
| Clima pasado (ERA5) | Copernicus CDS | Open-Meteo Archive (ERA5) | NASA POWER |
| Radiación para forraje | — | Open-Meteo | NASA POWER |
| Lluvia satelital | — | CHIRPS vía ClimateSERV (NASA/SERVIR) | ERA5 |
| Cobertura y deforestación | Global Forest Watch | Impact Observatory + ESA WorldCover (Planetary Computer) | — |
| Suelo y carbono | — | ISRIC SoilGrids | puntos vecinos a ~500 m |
| Focos de calor | NASA FIRMS (clave gratuita, 1 minuto) | — | — |
| Segunda opinión EUDR | Whisp (FAO), clave gratuita `WHISP_API_KEY`: crear cuenta en https://whisp.openforis.org, generar la clave en la cuenta (dura 365 días) | — | — |

Licencias: Open-Meteo y el plan Hobby de Vercel son de uso no comercial. Alcanza mientras DOTS no cobre; al empezar a cobrar, pasar a Open-Meteo API comercial y Vercel Pro.

## Estaciones de Brasil, Chile y Canadá

Las tres pantallas ya muestran datos. Con las claves pasan a la fuente nativa del país, en tiempo real.

| País | Sin clave (ya funciona) | Con clave | Cómo registrarse |
|---|---|---|---|
| Canadá | ECCC MSC GeoMet, tiempo real, abierta | — | No hace falta |
| Chile | METAR de aeropuertos chilenos (DMC, vía NOAA Aviation Weather Center), tiempo real | DMC red EMA en tiempo real: `DMC_USUARIO` (correo) y `DMC_TOKEN` | Crear cuenta en https://climatologia.meteochile.gob.cl (Iniciar sesión → registrarse), entrar a "Web Services" y copiar la API key personal |
| Brasil | METAR de aeropuertos brasileños (DECEA/REDEMET, vía NOAA Aviation Weather Center), tiempo real | INMET apitempo en tiempo real: `INMET_TOKEN` | Pedir el token a INMET desde https://portal.inmet.gov.br (Serviços → API / Fale conosco), indicando uso no comercial y el proyecto |

Cerca de una frontera se ven las estaciones del país vecino a menos de 300 km, siempre con su distancia: desde Corrientes, por ejemplo, el aeropuerto de Uruguaiana (Brasil).

Nota: NOAA ISD (Global Hourly) se probó y se descartó como respaldo porque su lista de estaciones dejó de actualizarse en agosto de 2025.
