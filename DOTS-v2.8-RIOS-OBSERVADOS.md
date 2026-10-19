# DOTS Campo v2.8 — Ríos observados (INA) y relevamiento de repos de clima e inundación

## Qué suma
**Nueva fuente observada: "Nivel y caudal del río" (`/api/fuentes/nivel-rio`)**, más una revisión de los
repositorios y servicios de clima, hidrología e inundación que evaluamos para el campo.

Hasta ahora el sistema tenía el **pronóstico** (GloFAS / Open-Meteo Flood API) y la **observación
satelital** (Copernicus GFM, Sentinel-1). Faltaba el **dato medido y oficial del río**: lo que hoy aporta
el INA (Instituto Nacional del Agua, DSIyAH) a través de su **API pública A5**
(`https://alerta.ina.gob.ar/a5`, abierta y **sin clave**).

El módulo toma el polígono del lote, busca las estaciones hidrométricas del INA dentro del recuadro,
ordena por cercanía al centro y devuelve, para las **4 más próximas**:

- **Último valor** observado, mínimo, máximo y **tendencia** (subiendo / bajando / estable).
- **Estado respecto de los umbrales** oficiales de la estación (`nivel_alerta`, `nivel_evacuacion`).
- **Altura hidrométrica (m)** y **caudal (m³/s)** del período (3 a 365 días, por defecto 30).
- Nombre del río y localidad de cada estación, con la **distancia al lote**.

En el panel se ve un gráfico con la serie del río y un recuadro con los umbrales y la última lectura.

## Cómo funciona
- `GET /obs/puntual/series?var_id=2&geom=minlon,minlat,maxlon,maxlat` → series de **altura** (`var_id` 2) y,
  con `var_id` 4, de **caudal**. El filtro geográfico es el parámetro **`geom`** (recuadro en
  `lon,lat` min/max); no acepta GeoJSON.
- `GET /obs/puntual/series/{id}?timestart=..&timeend=..` → observaciones de la serie (timestamps UTC).
- Se prefieren las series de **medición directa** y las de datos más recientes cuando una estación tiene
  varias series de la misma variable.

## Archivos
- `ina_a5.py` — conector: recuadro, series de altura y caudal, observaciones, resumen y tendencia.
- `research_routes.py` — entrada `'nivel-rio'` en `VEGETATION` y `import ina_a5`.
- `tests/test_ina_a5.py` — red simulada: referencia más cercana, serie, tendencia, umbral y ruta.
- `monitor.py`, `scripts/chequeo_vivo.py` — la fuente entra en el monitoreo y el chequeo en vivo.
- `src/main.tsx` — botón en el panel y vista "Nivel y caudal del río".

## Alcances
Es un dato **de la estación sobre el río**, no del lote: describe el contexto de crecida. Para estimar qué
superficie se inunda hacen falta relieve, umbrales locales y delimitación de la cuenca (otros módulos DOTS,
v2.1 y v2.2). Las alturas oficiales de alerta y evacuación las fijan Prefectura e INA; ante una evacuación
manda Defensa Civil.

---

## Relevamiento de repos y servicios (clima · hidrología · inundación)
Veredicto de qué nos sirve y qué no, con la licencia y las estrellas al día del relevamiento.

### Se integra
- **INA API A5** (`alerta.ina.gob.ar/a5`) — **integrada en v2.8**. Alturas y caudales observados, sin clave.
- **Google Flood Hub / Flood Forecasting API** (`floodforecasting.googleapis.com`) — cubre Argentina,
  Paraguay, Uruguay, Brasil y Bolivia. Requiere **lista de espera + API key**. Aporta pronóstico de crecida
  por punto. *(Sprint 1, previa inscripción.)*
- **`geoglows/pygeoglows`** (BSD-3) — GEOGLOWS ECMWF Streamflow, caudales por conjunto. Tarea offline
  (GitHub Actions), no en la ruta web.
- **`PratyushTripathy/AutoFloods`** (MIT) — detección de agua con SAR. **Se solapa** con `gfm.py` y `radar.py`;
  tomar solo ideas de umbralización, no integrarlo como capa nueva.

### Solo referencia / offline
- **LISFLOOD** (`ec-jrc/lisflood-code` EUPL-1.2, `andycarter-pe/lisflood2fim` BSD-3,
  `urabbani/lisflood-fp-sc` MIT) — modelo hidrológico-hidráulico. Pesado y offline; útil si algún día
  queremos simular la mancha de inundación del lote. Hoy no entra.
- **`google-research/flood-forecasting`** (Apache-2.0, "OpenHydroNet") — investigación ML. Sin herramienta lista.

### Se descarta
- **`keplergl/kepler.gl`** (MIT) — visor potente pero **se solapa con Leaflet** (el frontend ya usa Leaflet +
  ECharts + PMTiles).
- **`GeoNode/geonode`** — catálogo geoespacial completo; sobra para lo que necesitamos.
- **`marketimpact/pakistan-flood-data-platform-v2`** — de la plataforma no tomamos nada; sí la idea de usar la
  API de Google Flood Hub.
- **`loSpaccaBit/astro-landing-kit`** (MIT) — plantillas de landing en Astro; eventual inspiración de layout
  comercial para DOTS, nada técnico.
- **NASA Harvest** (`nasaharvest`: `presto`, `cropharvest` — **CC-BY-SA-4.0**, `galileo`, `crop-mask`,
  `glam-api`…) — es un **programa de investigación**, no una herramienta. Valor de contexto: el
  **GEOGLAM Crop Monitor**.

### Ya integrado (no volver a sumar)
- **GloFAS** — ya se consume vía **Open-Meteo Flood API** (`cuenca.py`, `cuenca_report.py`, job `rios`).
  Subir a Copernicus EWDS (`ewds.climate.copernicus.eu`, `cdsapi`) solo mejora la fidelidad del conjunto: bajo retorno.
- **GFM (Global Flood Monitoring)** — ya se consume en `gfm.py` (STAC EODC + WMS-T) y `cuenca_report.py`.

## Roadmap corto
1. **Google Flood Hub API** — inscribirse y guardar la clave; sumar como capa de pronóstico de crecida.
2. **Snow mask** en `vegetation.py` — **hecho (v2.0)**: fracción de nieve (SCL 11) por escena; con ≥10 % de
   nieve la escena se marca `nevada` y no se interpreta, así no hay falsos positivos de NDVI invernal.
3. **Mapa de rinde (pacu)** — **hecho**: `yield_map.py` (limpieza por σ + IDW), escala `yield_index`,
   ruta `POST /api/fuentes/mapa-rinde`. Faltan: **aptitud de cultivos (openfarm.earth)**,
   **MODIS+VIIRS VI (agwise)** y **agua vegetada** en `radar.py`.
4. **EarthAlign** — verificar la corrida de traducción (`captions_es` / `translated_to: 'es'`) y seguir con
   la Fase 2 (MeteoLIP) cuando haya torch + pesos + recorte ERA5.
