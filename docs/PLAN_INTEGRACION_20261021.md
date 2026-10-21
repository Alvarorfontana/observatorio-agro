# Integración DOTS — 21 de octubre de 2026

Rama de trabajo: `feature/dots-integracion-total-20261021`. Base: `main`.

## Objetivo
Consolidar y verificar módulos pendientes antes de un único merge a producción. No desplegar ni mezclar ramas sin comprobar compatibilidad.

## Módulos a auditar e integrar
- Mapa interactivo: capas, parcelas, radar, leyendas y gráficos.
- Crecidas: 34 localidades, población expuesta, cotas y radio de 15 km.
- Clima: ENSO, series históricas, pronósticos y fuentes.
- Agricultura: Sentinel, índices de vegetación, focos térmicos y análisis de lotes.
- Informes: PDF, gráficos, metadatos, fuentes y límites de datos.
- Infraestructura: Flask/Python, rutas API, dependencias, variables de entorno y despliegue.
- Cobertura geográfica internacional, con datos reales disponibles por región.

## Ramas candidatas (no fusionadas todavía)
`feature/dots-cierre-integraciones-20261019`, `feature/dots-radar-pronostico-informes`, `feature/gee-agricultura-precision`, `feature/radar-informes-graficos`, `feature/sentinel-1-scene-previews`, `integracion-clima-enso-v4`, `integracion-inpe-stac-gratuito`, `integracion-openfarm`, `modulo-evolucion-inundaciones`, `simulaciones-ambientales-base`, `suelos`, `rayos`.

## Condiciones de cierre
1. Revisar diferencias por rama y evitar sobrescrituras.
2. Integrar solo código comprobado; no sustituir resultados reales por datos simulados sin identificarlos.
3. Ejecutar pruebas API, compilación y navegación del mapa.
4. Verificar generación de PDF y estados de error.
5. Abrir PR hacia `main`; desplegar producción solo después de validación.

Estado inicial: rama y plan creados. Integraciones funcionales y pruebas pendientes.
