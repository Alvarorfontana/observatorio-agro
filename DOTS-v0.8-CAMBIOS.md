# DOTS Campo v0.8 — Reorganización territorial

## Implementado en esta iteración
- Identidad DOTS integrada: se retira el satélite caricaturesco del logotipo y se reemplaza por marca geométrica territorial.
- Portada: navegación reducida a Cómo funciona, Fuentes, Demo, Ingresar y Abrir Observatorio.
- Observatorio: rail/dashboard vertical izquierdo con módulos de lotes, satélites, vegetación, agua, suelos, ganado, clima, riesgos, ENSO e informes.
- Delimitación: accesos explícitos a Triángulo, Rectángulo y Polígono libre; cierre con superficie, perímetro y centroide.
- Marcadores territoriales: observación, ganado (hipótesis), incendio (hipótesis), temperatura/THI, agua/infraestructura y vegetación/anomalía. Se etiqueta la condición para no confundir hipótesis con dato confirmado.
- Selector satelital: se exponen accesos a MODIS, Sentinel-2, Sentinel-1, Landsat y VIIRS/FIRMS según los conectores existentes.
- Se corrige el texto de ESRI World Imagery: es un mosaico base y no una escena homogénea con una sola fecha.
- JSON pasa a llamarse Exportación técnica y queda visualmente secundario.
- El PDF puntual recibe polígono, superficie y perímetro en la solicitud para que el backend pueda vincular el informe al lote.

## Próxima capa técnica obligatoria
- Renderizar el polígono/mapa dentro del PDF, no sólo enviar sus coordenadas.
- Unificar PDF climático y PDF Agentic en un único Informe Territorial DOTS con gráficos y rangos de referencia.
- Añadir ENSO multifuente (IRI/Columbia, NOAA/CPC, BOM, JMA, ECMWF/C3S) como módulo propio.
- Incorporar CONAE/SAOCOM mediante servicios/productos oficialmente accesibles y mostrar su estado real de conexión.
- Procesar COG/STAC por polígono para NDVI/NDMI/EVI; no presentar índices si sólo existen metadatos de escena.
- Desarrollar páginas editoriales interiores completas con fotografía/cartografía/gráficos y la misma identidad de portada.

## Nota de build
La fuente TypeScript fue revisada, pero el build local no pudo completarse porque `npm ci` quedó incompleto en este entorno y faltaron paquetes `@types` (react, react-dom, leaflet, geojson, estree). Vercel deberá ejecutar una instalación limpia antes del build. No se debe interpretar esta nota como validación de despliegue.
