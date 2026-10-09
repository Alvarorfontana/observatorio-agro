# DOTS + OpenFarm — integración aislada, fase 1

## Alcance
Este paquete implementa un adaptador de meteorología Open-Meteo y validación básica de geometrías GeoJSON. **No instala ni integra el motor completo de OpenFarm**; no proporciona todavía NDVI, detección automática, PostGIS ni imágenes Sentinel. No cambia archivos existentes ni modifica producción.

## Archivos nuevos
- `api/openfarm-weather.js`: endpoint Vercel con datos actuales y pronóstico de 7 días de Open-Meteo.
- `src/services/openfarmAdapter.ts`: cliente y validación de polígonos.

## Instalación segura
1. Crear rama `feature/openfarm-integracion` desde la versión actual de `main`.
2. Copiar los dos archivos nuevos conservando rutas. Comprobar antes que no existan archivos con esos nombres.
3. Ejecutar `npm ci`, `npm run build` y los tests existentes.
4. Desplegar la rama únicamente como Preview en Vercel. No fusionar con `main`.
5. Probar `GET /api/openfarm-weather?lat=-28.5&lon=-59.0` en el preview.
6. Conectar una pantalla de lote a `fetchFieldWeather(lat, lon)` y usar `fieldFeature` al guardar polígonos.

## Advertencias
- Verificar que la configuración Vercel existente detecte `api/*.js` como funciones; una regla de rewrites podría interferir.
- El centroide debe calcularse geoespacialmente para polígonos complejos; no se incluye aquí.
- La validación comprueba estructura, cierre y coordenadas, pero no autointersecciones ni topología avanzada.
- Open-Meteo tiene condiciones de uso y límites; revisar licencia y condiciones para uso comercial.
- Esta fase no utiliza código copiado de OpenFarm; adopta su patrón modular y fuente meteorológica.
- El estado real del build y la compatibilidad con la aplicación requieren prueba sobre una copia del repositorio.

## Fase 2
Integrar adaptador STAC de Sentinel-2, índices NDVI/NDWI, tareas de procesamiento y detección FTW en servicio Python separado, con fuentes, calidad y fechas explícitas. Evaluar PostGIS y cola de tareas según carga real.
