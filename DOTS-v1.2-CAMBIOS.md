# DOTS Campo v1.2 — Corrección funcional y editorial

- Se agregaron botones funcionales del Observatorio para Copernicus S1/S2/S3, NASA MODIS, Landsat, CNES GEODES, DLR y Digital Earth Africa, además de Sentinel-1/2 y FIRMS.
- Los nuevos catálogos STAC ahora también se renderizan en el panel de resultados; antes podían existir en backend sin una salida visible equivalente.
- CNES GEODES fue corregido para consultar el endpoint oficial `/api/stac/items` documentado por CNES.
- Copernicus usa el endpoint STAC vigente `stac.dataspace.copernicus.eu/v1`.
- Se añadió logo DOTS Campo en SVG y se integró a la cabecera.
- Se ampliaron las páginas institucionales con qué es DOTS, qué es el Observatorio profesional, lógica de gestores/orquestación, trazabilidad, gestión ganadera y uso de múltiples fuentes.
- Se amplió Fuentes y Datos para explicar API conectada, credenciales, catálogos vs. procesamiento y control de calidad.
- El botón PDF se renombró a `Informe Territorial DOTS · PDF`.
- El PDF unificado conserva polígono, superficie/perímetro, indicadores y referencias, gráfico lluvia–ET0 cuando hay datos, hallazgos, ENSO, agua, recomendaciones, advertencias y trazabilidad.
- Validación backend: `py_compile` correcta.
- Validación PDF: generado y renderizado correctamente con un dataset explícitamente marcado como prueba de maquetación, no como medición real.
- El build React local no pudo completarse porque el entorno no contiene `node_modules`; Vercel debe ejecutar `npm ci`/build desde `package-lock.json`.
