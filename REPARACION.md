# Reparación del backend (8-oct-2026)

## Qué estaba roto
- `research_connectors.py` había sido reemplazado por una versión recortada: faltaban `variables`, `coordinates`,
  `polygon_bbox`, `platform_registry`, `image_bytes`, `ina_series`, `usgs_water`, etc. (los tests y el Blueprint los usaban).
- El backend de Vercel era FastAPI y nunca montaba `research_routes.py` (Flask): todas las rutas `/api/fuentes/<fuente>`,
  `tile`, `geocode`, `foto` y `analizar` daban 404 → botones en rojo, mapa sin tiles, sin PDF.
- `vercel.json` mezclaba `builds` con `buildCommand/outputDirectory` (Vercel ignora estos con `builds`).
- Había dos copias de `research_connectors`/`agentic_engine` (raíz y `api/`) y no estaba claro cuál se cargaba.
- `escenas.py` llamaba `c.scenes(..., max_results=)`, parámetro inexistente.

## Qué se hizo
- `research_connectors.py` reconstruido (contrato = el que esperan Blueprint, motor y frontend).
- `api/index.py`: app Flask única que registra `research_api`. Se eliminó el FastAPI y las copias duplicadas.
- `agentic_engine.py`: acepta `field_markers`; una fuente que responde `sin dato` ya no se cuenta como recibida.
- `vercel.json` simplificado (framework vite + rewrite `/api/*` → `/api/index`, maxDuration 60).
- FIRMS: la clave `FIRMS_MAP_KEY` ya no se incluye en `source_url`.
- `tests/test_routes.py`: 23 tests pasan (red simulada).

## NO verificado contra las APIs reales (revisar tras desplegar)
INA (`alerta.ina.gob.ar`), USGS OGC, SMN (`ws.smn.gob.ar`), INTA WMS (URL a confirmar), CNES/DLR/DE Africa STAC,
NOAA CDO y OpenAQ (validación con clave). Usá los botones de prueba del panel para confirmarlas una por una.

## Pendientes (devuelven error explícito, no datos falsos)
Agencias INMET, DMC, ECCC; fuentes con credencial sin conector end-to-end (solo detectan la variable).
