# DOTS — Lote de publicación climática (21-10-2026)

## Preparado en rama `diag-lote-clima-20261021`
- Monitor global de récords térmicos: `/clima/records-termicos/`.
- Mapa OpenStreetMap/Leaflet con búsqueda de país o región; filtros de récord / a menos de 1 °C / resto.
- Importación local CSV validada, tabla, marcadores, exportación CSV e impresión/PDF del navegador.
- Acceso desde el espacio ambiental principal.
- Sin valores térmicos inventados ni reclamo de ingesta oficial automática.

## Pendiente de conectar o verificar antes de afirmar que está completo
1. **ENSO global:** el observatorio NOAA/IRI ya está en `src/site/EnsoObservatory.tsx`. Falta obtener y normalizar los pronósticos ACCESS-S2 y otras series con licencia/fuente verificadas; distinguir R-Niño3.4, ONI y SST absoluta; asociar teleconexiones fundamentadas por país. No convertir capturas en series numéricas.
2. **Récords térmicos:** integrar fuentes oficiales por país, cobertura de estaciones, climatología, metadatos, fechas y polígonos administrativos. La vista nueva permite analizar CSV reales, pero NO está conectada aún a IDEAM/SMN/INMET.
3. **Población / crecidas:** comprobar en navegador que aparecen mapa y gráficos y que `POST /api/poblacion/crecida/informe` devuelve un PDF válido con datos reales. Los cambios anteriores en `main` aún requieren validación en producción.
4. **Pruebas:** ejecutar `npm ci && npm run build` y las pruebas Python del repositorio en CI o entorno con dependencias; inspeccionar funcionamiento móvil, enlaces externos, CSP y PDF.
5. **Publicación:** no desplegar por cada commit. Mantener cambios en rama excluida de Vercel mediante `git.deploymentEnabled`. Tras pruebas, fusionar una vez a `main` y verificar UN despliegue de producción y sus rutas. El límite de Vercel puede impedirlo hasta su restablecimiento.

## CSV esperado
`pais,localidad,lat,lon,fecha,observada_c,record_c,fuente`

La clasificación usa diferencia observada menos récord: >= 0 récord igualado/superado; (-1,0) cerca; <= -1 resto. La unidad es °C y la comparación exige serie homogénea.
