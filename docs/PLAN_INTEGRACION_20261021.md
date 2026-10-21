# DOTS — Integración única sin Vercel

Rama: `feature/dots-integracion-total-20261021`. No usar Vercel, no desplegar, no publicar cambios parciales. Mantener `main` intacta durante el trabajo.

## Alcance completo
1. Mapa geoespacial interactivo: capas, parcelas, búsqueda, controles, leyendas y gráficos.
2. Inundaciones y población: 34 localidades ribereñas, radio de 15 km, cotas, exposición y datos con procedencia verificable.
3. Radar Sentinel-1, MODIS, GloFAS y detección de cambios con fechas y límites metodológicos.
4. Clima y ENSO, series históricas y registros térmicos con fuentes.
5. Agricultura de precisión: Sentinel, índices de vegetación, análisis de lotes y fuentes INPE/STAC.
6. Informes PDF, gráficos, exportaciones y respuestas de error.
7. API Flask/Python, frontend React/Vite, rutas, dependencias, pruebas y documentación.

## Criterios de trabajo
- Consolidar código por archivo, comparando implementaciones anteriores sin fusiones indiscriminadas.
- No presentar datos simulados como mediciones.
- Evitar servicios de publicación y despliegue; realizar pruebas locales o CI en GitHub cuando estén disponibles.
- Entregar una sola rama consolidada y un resumen de pruebas, limitaciones y pendientes reales.
- No fusionar con `main` sin revisión final.

Estado: alcance aprobado; integración de código y validación aún pendientes.
