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

## Ya configurada previamente
- NASA FIRMS: `FIRMS_MAP_KEY`

Los botones protegidos están programados para informar `requiere credencial` hasta que Vercel tenga las variables. Tener la variable configurada no equivale todavía a certificar el dato: la fuente pasa a OPERATIVA sólo después de una consulta real válida.
