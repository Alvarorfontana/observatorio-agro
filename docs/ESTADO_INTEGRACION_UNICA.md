# Estado de integración DOTS — 21/10/2026

Rama de trabajo: `feature/dots-integracion-total-20261021`.

## Ya integrado en esta rama
- Conector de metadatos de escenas INPE/STAC: `inpe_stac.py`.
- Pipeline de análisis raster Sentinel-1: `scripts/radar_raster_pipeline.py` (dependencias raster externas y datos reales necesarios).
- Monitor de récords térmicos con CSV y mapa: `public/clima/records-termicos/index.html`.
- Enlace desde `src/site/EnvironmentalWorkspace.tsx` al monitor.
- Pruebas de rutas de población y generación de PDF: `tests/test_population_routes_smoke.py`.
- Configuración para evitar despliegues de esta rama en Vercel; NO se utiliza Vercel en esta integración.

## Existía ya en la base y requiere validación
- Mapa ambiental, capas, selección de tramos y escenarios de inundación.
- API de población ribereña, 34 localidades previstas, Earth Engine, HAND y WorldPop.
- Informe PDF de exposición y radar, agricultura de precisión, ENSO.
- Integraciones con servicios externos: su respuesta real depende de conectividad, credenciales y cobertura.

## Pendiente de cierre
1. Ejecutar y corregir compilación TypeScript/Vite y pruebas Python.
2. Comprobar que el módulo de población se registra al iniciar la API y que las 34 localidades responden.
3. Probar mapa y gráficos en navegador, incluyendo móviles.
4. Validar accesos a datos oficiales y dependencias de procesamiento Sentinel-1.
5. Integrar selectivamente mejoras antiguas sin reemplazar implementaciones más recientes.
6. Documentar fallos reales, aprobar una única fusión a main; sin despliegue.

No se considera terminado hasta obtener pruebas satisfactorias. No atribuir al sistema datos que no haya medido.
