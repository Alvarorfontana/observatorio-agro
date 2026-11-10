# DOTS — Estado real de Agricultura de Precisión

**Fecha:** 10 de noviembre de 2026  
**Rama:** `feat/dots-vision-suelos-territorio`  
**Producción:** pendiente de revisión y merge del PR #58.  
**Presupuesto:** cero; no habilitar proveedores, credenciales o servicios que generen cargos.

Este documento separa implementación, pruebas automáticas y validación agronómica. Un test aprobado no equivale a comprobar una fuente externa en un lote real.

## Estado por componente

| Componente | Implementado en la rama | Límite / validación pendiente |
|---|---|---|
| Geometría del lote | Dibujo de polígono, cálculo geodésico de superficie y consultas zonales | No hay aún validación de inventario de múltiples lotes en lote masivo ni contraste de cada geometría con catastro |
| Sentinel-2 | NDVI L2A vía Microsoft Planetary Computer, máscara SCL de nube/nieve, estadísticas y overlays RGB/NDVI | Depende de escenas despejadas y disponibilidad externa; falta prueba visual real en Vercel para polígonos de distinto tamaño |
| Índices | EVI, SAVI, NDMI y NDWI mediante Sentinel-2; endpoint de índices espectrales | Revisar disponibilidad por escena y no interpretar índices como rendimiento o diagnóstico |
| Histórico MODIS | NASA ORNL DAAC MOD13Q1, compuestos de 16 días, hasta cinco años en la ruta pública | Resolución de 250 m; es contexto de vegetación de una ventana centrada en el lote, no historia intralote de 10 m ni clasificación de cultivos |
| Historia agrícola | Existen conectores de cobertura/MapBiomas y cambios, algunos dependientes de Earth Engine | **No está terminado como historial fiable de cultivos y rotaciones por lote** en el flujo gratuito predeterminado |
| Ambientes | K-means de tres zonas sobre histograma NDVI de una escena Sentinel-2; superficie estimada por zona | Son zonas de vigor relativo de esa fecha, no ambientes productivos permanentes. Falta estabilidad multitemporal y contraste de campo |
| Suelos | SoilGrids y capas de suelos existentes; carta INTA 1:50.000 en ámbito geográfico disponible | SoilGrids es modelado y puntual/grillado, no análisis de laboratorio. La carta INTA no cubre todas las regiones |
| Agua | Balance hídrico y perfil ERA5-Land; humedad SAR y análisis de agua/riesgo existentes | ERA5-Land es grilla de ~9 km, no medición intralote. Radar requiere interpretación específica; caudal GloFAS no es nivel ni mapa de inundación |
| Clima | Open-Meteo/ERA5, CHIRPS, NASA POWER, índices agroclimáticos y pronósticos | Distinguir observación, reanálisis y pronóstico; las grillas no describen microclimas del lote |
| Informe técnico | Generador Typst/ReportLab; interpretación redactada de NDVI; el botón de la página solicita el PDF al backend | Falta comprobar PDF generado desde la página desplegada con fuentes reales y datos de varios lotes |
| Validación por lote | La página incorpora chequeo de respuestas de Sentinel-2, MODIS, zonas, índices, suelo, balance y radar | Es una validación de disponibilidad/contrato, no certificación de exactitud ni reemplazo de recorrida agronómica |

## Reglas de interpretación

- No presentar NDVI como biomasa, sanidad o rendimiento.
- No llamar «ambiente productivo» a una clasificación de vigor de una sola escena.
- No afirmar cultivo o rotación sin una fuente de clasificación y validación temporal.
- No inferir compactación, fertilidad ni agua disponible medida a partir de SoilGrids.
- Marcar como «sin dato» las fuentes sin respuesta; no reemplazar ausencias por cero.
- En cada mapa indicar sensor, fecha, resolución, cobertura válida, escala y método.
- No usar GEE, Sentinel Hub, openEO ni servicios GPU que impliquen credenciales pagas o facturación. Si una fuente gratuita exige credencial o no responde, informar el límite.

## Criterio para declarar terminado

1. Tests de geometría, índices, nubes/nieve, fechas, valores faltantes, series y regresión aprobados.
2. Consultas reales a fuentes públicas verificadas con al menos un lote de prueba conocido.
3. Mapas Sentinel-2 y zonas superpuestos correctamente sobre la geometría en escritorio y móvil.
4. Validación separada de lotes pequeños y grandes, y lotes fuera de Buenos Aires.
5. Histórico de cultivos/rotaciones sustentado por una fuente abierta real, no inferido sólo de NDVI.
6. Ambientes estables comprobados en varias fechas/campañas y, cuando se formulen recomendaciones, contrastados con datos de campo.
7. PDF completo generado desde la interfaz con trazabilidad, interpretación, limitaciones y datos reales.
8. CI completo y revisión de no-regresión aprobados.
9. PR revisado; no hacer merge ni despliegue sin autorización.

