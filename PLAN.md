# PLAN de DOTS — próximos pasos

Última actualización: 2026-10-18.
Este archivo sirve para retomar el trabajo sin releer toda la conversación. Se puede borrar o actualizar cuando ya no haga falta.

## Estado (hecho y en `main`)

- Panel público + informes/newsletters por tema (`temas.py`, `informe_temas.py`, `scales.py`).
- Asesor: agua (FAO-56), nitrógeno, aire, pulverización, enfermedad, vegetación.
- Agua/crecidas: cuenca, GloFAS, INA, amenaza por período de retorno (`hazard.py`), El Niño.
- Página `/nino-crecidas` (web) + workflow cada 2 h (digest + newsletter).
- Humedad satelital SMAP (`smap.py`, L4 v008): superficie y raíz, percentil; escalas `soil_moisture_vwc` y `soil_moisture_pctl`.
- Rendimiento esperado por agua (FAO-33): `yield_forecast.py`, escala `yield_pct`, tema `rendimiento`, ruta `/api/fuentes/rendimiento`.
- Mapa de rinde del lote (`yield_map.py`): puntos del monitor de cosecha, limpieza por σ e IDW; escala `yield_index`, ruta `POST /api/fuentes/mapa-rinde`.
- `NOTA-DE-PRENSA.md` (faltan teléfono, correo de prensa y fecha de inicio).
- Último commit en `main`: `f87f3c3`. `pytest`: 361 passed, 2 skipped.

## Rendimiento esperado por agua (FAO-33) — hecho (v1.0)

Objetivo: un módulo que estime el **rendimiento relativo** de la campaña (Ya/Ym) con `yield_forecast.py`.

- Método: FAO-33 (Doorenbos y Kassam, 1979): `Ya/Ym = 1 − Ky · (1 − ETa/ETm)`.
  - ETm = Σ Kc·ET0 (máximo del cultivo); ETa = Σ Ks·Kc·ET0 (limitado por agua).
  - Balance hídrico FAO-56 diario (secano, sin riego): `Dr,i = Dr,i−1 − P + ETc,aj` (DP cuando Dr<0).
  - Reutilizar `crop_water.kc_for_day`, `crop_water.stage`, `crop_water.taw_mm` y la curva de Kc por cultivo.
- Datos: ET0 y lluvia observadas (Open-Meteo Archive, ERA5) hasta ~6 días atrás + pronóstico (Open-Meteo, 10 días)
  + el resto de la campaña rellenado con **climatología ERA5** del mismo día del año. Agua útil del suelo: SoilGrids
  (`wv0033`, `wv1500`).
- Coeficientes Ky por cultivo (FAO-33): maíz 1,25 · soja 0,85 · trigo 1,15 · girasol 0,95 · sorgo 0,90 · alfalfa 1,10 · pastura 1,00.
- Entradas: `lat`, `lon`, `crop`, `sowing` (obligatoria) y opcional `potencial_t_ha`.
- Salidas: `relative_yield_pct`, `etc_max_mm`, `etc_actual_mm`, `water_deficit_mm`, `expected_t_ha` (si hay potencial), `reading`.
- Escala nueva: `yield_pct` (0–100, `high_ok`; bandas <50 riesgo, 50–70 bajo, 70–90 bueno, >90 cercano al potencial).
- Tema nuevo: `rendimiento` (grupo Cultivo, `scope: punto`, resolver con `crop`/`sowing` de los params).
- Ruta: `GET /api/fuentes/rendimiento?lat=&lon=&crop=&sowing=&potencial_t_ha=`.
- Tests: `tests/test_yield_forecast.py` (expresión/balance, sin siembra → sin dato, sin suelo → sin dato, relativo
  monótono con el agua, escalas, tema y endpoint). Correr `python -m pytest -q` (meta > 361 passed).
- Caveats a incluir: es una estimación por agua (no pronóstico de cosecha), asume secano, el futuro usa climatología.

## Mapa de rinde del lote (pacu) — hecho (v1.0)

Objetivo: a partir de los puntos del monitor de cosecha, armar un mapa de rinde relativo al lote (`yield_map.py`).

- Flujo "simple" de pacu (dos Santos y Miguez): validar puntos, limpiar por desvío estándar (fuera de
  media ± 3σ y rindes ≤ 0) e interpolar por distancia inversa (IDW, p=2) sobre una grilla regular.
- Entradas (POST JSON): `points` ([[lat,lon],...], 5 a 5000), `values` (mismo largo), `boundary` opcional
  ([[lat,lon],...]) y `cell_m` (2 a 100 m; por defecto 10). Tope de 2500 celdas (agranda la celda si hace falta).
- Salidas: `mean`, `median`, `min`, `max`, `sd`, `cv_pct`, `removed` (nulos/atípicos), `n_used`, `cells`
  (cada celda con `value` e `index` relativo a la media), `area_ha` y `reading`.
- Escala nueva: `yield_index` (0–200, `high_ok`; 100 = media del lote). Ruta: `POST /api/fuentes/mapa-rinde`.
- Tests: `tests/test_yield_map.py`. Caveat: mapa relativo, no absoluto ni oficial; sin corrección por humedad.

## Newsletter "El Niño y crecidas" (qué falta para que salga correo solo)
Ya está el workflow `.github/workflows/nino-crecidas.yml` (cron `23 */2 * * *` + `workflow_dispatch`) con
`scripts/nino_crecidas.py` (digest JSON+HTML+PDF) y `scripts/nino_newsletter.py` (envío por Resend, una vez por
día con UTC ≥ 8; `NINO_FORZAR=1` fuerza; gate `enviado_el`). Los datos van a la rama `datos` (no se publica la web).

Pendiente, todo del lado de secretos y disparo:

1. Cargar secrets en GitHub → Settings → Secrets → Actions:
   - `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, `AVISOS_FROM`.
   - (Para los avisos en la web/Vercel también: `RESEND_API_KEY` y `RESEND_AUDIENCE_ID` en Vercel.)
2. Disparar una vez a mano: Actions → "El Niño y crecidas (digest y newsletter)" → Run workflow
   (para probar el envío y para que exista el primer `data/nino_crecidas.json` en la rama `datos`).
3. Verificar: que llegue el correo, que el PDF se genere 1×/día y que la rama `datos` guarde los archivos.
4. Sin `RESEND_*` el script no rompe: guarda y reporta "sin configurar" (deja el correo para cuando estén las claves).

## Otros pendientes del roadmap

- Informes por audiencia (gobierno / municipio / empresa): plantillas y estándares (ODS, Sendai, GHG/GRI/CSRD/ISSB/TNFD).
  Es el entregable vendible; es más grande (backend + front).
- Exponer SMAP en la web: panel de humedad satelital en la página de cultivo/nivel de lote (además de la API).
- Refactor de `src/main.tsx` por etapas (monolito).
- Escalas pendientes si se agregan esos módulos: `pest_risk`, `soc_gkg`, `soil_ph`, `cec_cmol`, `clay_pct`.

## Cómo trabajar (rápido, para la próxima sesión)

- Tests: `python -m pytest -q` (desde la raíz del repo). Lint web: `npm run lint`. Build: `npm run build`.
- Commit (git global sin user): `git -c user.name="Alvaro Fontana" -c user.email="alvarofontana@gmail.com" commit -m "..."`.
- Push: `git push origin mejoras-bundle` y luego `git push origin mejoras-bundle:main` (fast-forward a `main`).
- No commitear el churn de `dist/`. `curl.exe` no conecta en este entorno; sí `Invoke-WebRequest`.
- En este entorno no se pueden dejar procesos vivos (Flask/Vite se cortan al terminar el comando); para ver local:
  terminal 1 `python -m flask --app api.index run --port 8000`, terminal 2 `npm run dev`, abrir `http://localhost:5173`.
