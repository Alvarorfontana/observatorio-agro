# DOTS — Pendientes verificados (21-10-2026)

## Etapa 1 — mapa, inundaciones, población
- Comprobar navegación y renderizado real de `src/site/EnvironmentalWorkspace.tsx` y `public/radar/index.html` en escritorio y móvil.
- Comprobar que las 34 localidades están efectivamente cargadas; verificar georreferenciación, radio de 15 km, cota, población y procedencia de cada fuente. No declarar cifras sin datos.
- Probar `POST /api/poblacion/crecida/informe` y validar tipo MIME, estructura y contenido del PDF.
- Confirmar instalación de `pyclipper`: `api/index.py` omite registrar `population_bp` ante `ImportError`, por lo que puede faltar la API sin que falle el health check.
- Separar visualización topográfica de inundación observada y de pronóstico hidrológico.

## Etapa 2 — radar, clima, agricultura e informes
- Revisar diferencias por archivo en ramas radar, Sentinel-1, GEE, ENSO, simulaciones e INPE; no fusionar ramas completas obsoletas.
- Validar Sentinel-1 y productos NASA con fechas, cobertura y errores explícitos.
- Verificar ENSO NOAA/IRI y fuentes oficiales de récords térmicos; no presentar CSV manual como ingesta automática.
- Verificar agricultura, índices espectrales, geometrías y PDF de informes.

## Etapa 3 — pruebas y publicación
- `npm ci && npm run build`; pruebas Python con dependencias instaladas.
- Probar rutas `/`, `/radar`, `/agricultura-precision`, `/poblacion`, `/api/health`, y endpoints de informes.
- Probar navegación móvil, gráficos, capas y manejo de errores de servicios externos.
- Comprobar configuración `vercel.json` y exclusión de despliegues de ramas de trabajo; abrir PR a `main` solo con cambios validados.

## Estado
Este documento es una auditoría y lista de comprobación; no certifica que las integraciones funcionales ni las pruebas estén completas. Rama base: `feature/dots-integracion-total-20261021`.
