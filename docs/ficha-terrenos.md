# Ficha única de terrenos

Módulo integrado al Observatorio (`/observatorio`), sin nueva página ni nuevo proveedor.

- **Tablero:** después de la identificación del lote y antes de los gráficos.
- **Mapa:** ficha al final del área de análisis; accesos a WorldCover, humedad SMAP y crecidas junto al mapa, con descripción, fecha y opacidad.
- **Comparar terrenos:** dentro de la ficha; de dos a cuatro lotes guardados, columnas con fecha, fuente y escala de cada variable. No asigna un puntaje de aptitud.

La ficha combina los conectores existentes de clima, NDVI, SoilGrids y sustentabilidad. Reutiliza respuestas identificadas con el mismo punto y polígono; el botón de actualización vuelve a consultar las cuatro fuentes. Los resultados de comparación se consultan por lote, con las cuatro fuentes en paralelo. Las respuestas tardías de otro lote no se incorporan al panel activo.

Las fichas se guardan en este navegador y pueden descargarse en JSON, con geometría y metadatos. El botón PDF abre el generador territorial existente para el lote activo; no genera un PDF de comparación. Una consulta interrumpida al cerrar la página queda disponible para reintentar.

## Alcance de los datos

- SoilGrids: perfil puntual modelado a 250 m; se declara si el conector usó un punto vecino. Propiedades a 0–5 cm y agua útil derivada a 0–60 cm.
- WorldCover: proporciones de árboles, pastizal y cultivos de 2021 dentro del lote. No son todas las clases ni una medición actual.
- NDVI: promedio del polígono y fecha de la imagen.
- Clima: grilla en el punto del lote, con fecha/período. Un acumulado con días faltantes permanece sin dato.
- Un valor cero es un dato válido. Una fuente fallida se muestra como sin dato.

## Verificación

- `npm run build`: tipos y compilación de producción.
- `npx oxlint src/dashboard/TerrainSheet.tsx src/dashboard/terrainSheetModel.ts`: componentes nuevos.
- `node --experimental-strip-types --test tests/terrain_sheet.test.mjs`: valores cero, faltantes, cobertura parcial, identidad espacial y fechas.
- Prueba de interacción en DOM: cambio de lote durante una consulta, aislamiento de respuestas tardías, comparación y persistencia.

La consulta de producción no pudo verificarse: Vercel devuelve protección SSO y el conector conectado respondió 403 al intentar acceder al proyecto. No se modificó la protección.

## Revisión visual local

Se abrió la interfaz en Chromium con respuestas de ejemplo rotuladas como demostración. Se capturaron ficha, gráficos, comparación y mapa base satelital. Se corrigieron el encuadre del mapa al salir de Tablero y el panel de capas: ahora es plegable, permite leer su descripción y no estira los controles sobre el mapa.

La prueba móvil a 390 px no mostró desbordamiento horizontal ni errores de JavaScript; el mapa volvió a encuadrar el lote a zoom 12. Esto valida la interfaz; no acredita respuestas reales de SoilGrids, NDVI ni WorldCover en producción.

Se preparó un primer recorrido visual de 63 segundos, 1920 × 1080, con subtítulos y reproductor por capítulos. Usa capturas de la interfaz y datos de ejemplo; no es una grabación de análisis en producción. La locución profesional sigue pendiente.
