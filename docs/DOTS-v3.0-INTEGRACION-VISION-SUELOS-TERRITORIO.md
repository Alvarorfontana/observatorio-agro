# DOTS v3.0 — integración de visión artificial, territorio 3D y diagnóstico de suelos

**Rama:** `feat/dots-vision-suelos-territorio`  
**Base:** `main`  
**Alcance geográfico:** Argentina, Brasil, Uruguay y Paraguay.  
**Estado:** diseño de integración versionado; todavía no declara modelos operativos ni despliega servicios.

## Objetivo

Incorporar las tres líneas identificadas en la revisión: (1) detección y seguimiento de ganado con YOLO26 + BoT-SORT, (2) visualización geoespacial 3D inspirada en las capacidades de OSIRIS, y (3) diagnóstico agronómico de riesgo de compactación del suelo basado en mediciones y evidencia científica sobre respuestas radiculares.

La integración debe reutilizar la arquitectura existente de DOTS (React/Leaflet/ECharts y API Python/Flask), no crear un segundo Observatorio ni reemplazar el visor actual sin una prueba comparativa.

## Principios obligatorios

1. No se declara operativo un modelo por instalar una dependencia, añadir una pantalla o encontrar un repositorio.
2. Separar datos observados, productos satelitales, inferencias de IA, estimaciones y simulaciones.
3. Cada resultado debe incluir fuente, fecha de adquisición/procesamiento, unidad, geometría o área de referencia, versión del modelo y limitaciones.
4. No fabricar detecciones, valores de compactación, identidades de animales ni mapas de inundación.
5. Procesamiento pesado fuera de Vercel y de la computadora del usuario. La web consulta resultados y trabajos asíncronos.
6. No almacenar videos de establecimientos ni credenciales en el repositorio. Usar URLs firmadas o almacenamiento privado y secretos de entorno.
7. Mantener el alcance regional de DOT: Argentina, Brasil, Uruguay y Paraguay.
8. No fusionar a `main`, desplegar ni modificar producción como parte de esta rama.

## Línea A — Ganadería con YOLO26 y seguimiento multiobjeto

### Componentes
- YOLO26: detección de objetos/animales en fotogramas; seleccionar variante pequeña para la primera prueba.
- BoT-SORT: seguimiento temporal dentro de una secuencia de video.
- ByteTrack: alternativa para benchmark con las mismas secuencias.

### Funciones objetivo
- Conteo de entradas/salidas por línea virtual.
- Seguimiento temporal por cámara y sesión.
- Ocupación y densidad observada de corrales.
- Tiempo de permanencia y trayectorias agregadas.
- Alertas de baja confianza, oclusión, pérdida de track y cámara fuera de servicio.

### Límite científico/técnico
El ID de BoT-SORT es un identificador de track dentro de una secuencia, no una identidad permanente del animal entre días o cámaras. La reidentificación requiere un módulo independiente y validación con caravanas/RFID o un conjunto de datos etiquetado. No inferir salud, bienestar ni identidad individual a partir de detección genérica.

### Arquitectura prevista
- Servicio de inferencia externo con GPU, independiente del frontend y de las funciones serverless.
- API autenticada para crear trabajos, consultar estado y recuperar resultados.
- Resultados compactos: conteos, tracks anonimizados, timestamps, métricas de confianza y polígonos/zonas; el video original permanece privado.
- Prueba inicial con videos autorizados y anotaciones manuales; comparar YOLO26n + BoT-SORT frente a YOLO26n + ByteTrack.

### Criterios para habilitar producción
- Dataset de validación representativo de luz, barro, polvo, oclusiones y densidad de animales.
- Métricas: precision, recall, mAP, IDF1/HOTA, error de conteo y latencia.
- Revisión de licencia de código, pesos y uso comercial de Ultralytics antes de cualquier despliegue.
- Umbrales definidos a partir de validación; no inventar un porcentaje de precisión.

## Línea B — Territorio 3D y capacidades de OSIRIS

### Decisión de arquitectura
OSIRIS se evalúa como referencia/plataforma externa, no se copia ni se incorpora como dependencia central automáticamente. El repositorio DOTS ya dispone de Leaflet, ECharts, PMTiles y conectores de relieve/hidrología; por eso se conservará el visor actual y se hará una prueba aislada de MapLibre GL JS/WebGL para terreno 3D antes de decidir.

### Capas y productos posibles
- Modelo digital de elevación y sombreado del relieve.
- Pendiente, orientación, acumulación de flujo y cuencas.
- Red hidrográfica y puntos de observación oficiales.
- Máscaras de agua/inundación observada por radar Sentinel-1/GFM.
- Escenarios de inundación únicamente si se incorpora un modelo hidráulico/hidrológico validado y sus parámetros.

### Fuentes candidatas
- Copernicus DEM u otro DEM con licencia y resolución documentadas.
- MERIT Hydro para red de drenaje y variables derivadas.
- Sentinel-1 y Copernicus Global Flood Monitoring para observación de agua.
- GloFAS/Open-Meteo Flood e INA A5 para pronóstico/observación fluvial, conservando su naturaleza diferenciada.

### Restricción
Una visualización 3D o una animación de agua no es, por sí sola, una simulación hidrológica. No mostrar niveles, caudales ni superficies futuras sin datos, método, calibración y validación explícitos. Reutilizar conectores existentes; no duplicar GFM, Sentinel-1 o GloFAS ya integrados.

## Línea C — Diagnóstico de compactación y respuesta radicular

### Qué es y qué no es
La publicación científica sobre compactación, etileno y respuestas de las raíces aporta fundamento biológico; no es un modelo predictivo listo para ejecutar ni permite medir etileno desde satélite.

### Variables admisibles
- Densidad aparente (con unidad y profundidad).
- Resistencia a la penetración (con unidad, humedad y profundidad).
- Humedad del suelo.
- Infiltración medida.
- Textura, materia orgánica y profundidad efectiva, identificando fuente y escala.
- Cobertura/uso del suelo y series satelitales como contexto, no como sustitutos de mediciones físicas.

### Producto DOT
Ficha por lote y mapa de riesgo/limitaciones físicas solo cuando existan suficientes datos de campo o fuentes documentadas. Mostrar dato faltante como faltante; no completar con promedios inventados. No inferir concentración de etileno, grosor de raíces ni compactación exacta a partir de NDVI o imágenes satelitales.

### Validación
Contrastar las estimaciones con mediciones de penetrómetro, densidad aparente e infiltración georreferenciadas. Documentar profundidad, humedad al medir, protocolo, fecha y laboratorio/equipo.

## Integración con la plataforma existente

- Frontend: nuevos paneles dentro de DOTS; mantener React, Leaflet y ECharts. MapLibre queda en prototipo aislado hasta superar comparación funcional y de rendimiento.
- API: Flask existente; endpoints nuevos bajo prefijo `/api/dots/` solo después de definir autenticación, límites, esquemas y pruebas.
- Procesamiento: tareas externas asíncronas para inferencia de video y cálculos geoespaciales pesados.
- Persistencia: metadatos y resultados derivados; videos y credenciales fuera del repositorio.
- Observabilidad: registrar estado de trabajo, versión del modelo, errores, duración y procedencia.
- Informes: PDF/CSV con procedencia y advertencias de alcance.

## Secuencia de implementación

1. **Inventario y pruebas de compatibilidad:** identificar módulos, rutas, capas y dependencias existentes; no duplicar funciones.
2. **Prototipo de ganadería:** benchmark con videos autorizados, YOLO26n + BoT-SORT vs ByteTrack; medir calidad y coste externo.
3. **Prototipo de terreno 3D:** comparar MapLibre con Leaflet en una cuenca argentina y un lote, con DEM real y atribución.
4. **Ficha de suelos:** definir esquema de observaciones de campo y cálculo transparente; sin puntuación hasta tener datos y validación.
5. **Integración UI/API:** conectar solo componentes que hayan pasado pruebas y revisión de seguridad/licencias.
6. **Revisión:** pruebas automatizadas, verificación de fuentes reales y revisión visual en escritorio/móvil. PR separado; nunca desplegar automáticamente desde esta rama.

## Estado de certificación

| Línea | Estado actual | Evidencia necesaria para pasar a operativa |
|---|---|---|
| YOLO26 + BoT-SORT | Pendiente de prototipo | Video autorizado, inferencia ejecutada, métricas y coste |
| ByteTrack comparativo | Pendiente | Benchmark sobre el mismo conjunto de validación |
| MapLibre/terreno 3D | Evaluación | DEM real, rendimiento móvil/escritorio y comparación con Leaflet |
| Compactación del suelo | Diseño científico | Mediciones de campo trazables y validación |
| OSIRIS como plataforma completa | No adoptada | Auditoría independiente de código, APIs, licencia, seguridad y solapamiento |

## Referencias de partida

- YOLO26: https://docs.ultralytics.com/models/yolo26/
- Seguimiento Ultralytics (BoT-SORT/ByteTrack): https://docs.ultralytics.com/modes/track/
- OSIRIS: https://github.com/simplifaisoul/osiris
- MapLibre GL JS: https://maplibre.org/maplibre-gl-js/docs/
- Copernicus DEM: https://dataspace.copernicus.eu/
- MERIT Hydro: https://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/
- Copernicus Global Flood Monitoring: https://global-flood.emergency.copernicus.eu/
- SoilGrids: https://soilgrids.org/

---
**Nota de rigor:** este documento registra la decisión y el diseño de integración. No significa que las inferencias de ganado, la vista 3D, ni un diagnóstico de compactación estén ya ejecutándose o validados en DOTS.
