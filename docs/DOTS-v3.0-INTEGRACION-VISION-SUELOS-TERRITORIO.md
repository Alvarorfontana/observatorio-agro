# DOTS v3.0 — módulos adicionales de visión artificial, territorio 3D y diagnóstico de suelos

**Rama:** `feat/dots-vision-suelos-territorio`  
**Base:** `main`  
**Alcance geográfico:** Argentina, Brasil, Uruguay y Paraguay.  
**Estado:** diseño de integración versionado; todavía no declara modelos operativos ni despliega servicios. **Modalidad obligatoria: ampliación aditiva; no reemplazar, reescribir, retirar ni alterar el comportamiento de los módulos DOTS existentes.**

## Objetivo y regla de preservación

Incorporar las tres líneas identificadas en la revisión como módulos nuevos, aislados e integrados al menú y al flujo existente. **No modificar la lógica, fuentes, pantallas, rutas, cálculos, estilos ni contratos de los módulos actuales**, salvo los puntos mínimos de conexión necesarios para mostrar los módulos nuevos. No refactorizar ni migrar módulos existentes como parte de esta entrega. Cada ampliación debe poder retirarse sin afectar las funciones previas.

Las tres líneas identificadas en la revisión son: (1) detección y seguimiento de ganado con YOLO26 + BoT-SORT, (2) visualización geoespacial 3D inspirada en las capacidades de OSIRIS, y (3) diagnóstico agronómico de riesgo de compactación del suelo basado en mediciones y evidencia científica sobre respuestas radiculares.

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

## Integración con la plataforma existente (sólo aditiva)

- Preservación: los módulos, rutas, capas, cálculos, APIs y pantallas actuales permanecen intactos. La nueva funcionalidad se incorpora en componentes, servicios, endpoints y rutas propios; los cambios al menú/router se limitan a añadir accesos y puntos de montaje.
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
6. **Revisión:** pruebas automatizadas, verificación de fuentes reales y revisión visual en escritorio/móvil. Comprobar explícitamente que no haya regresiones en los módulos preexistentes. PR separado; nunca desplegar automáticamente desde esta rama.

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


## Alcance funcional ampliado acordado — módulos nuevos para incorporar

Esta sección incorpora el conjunto de funcionalidades conversadas para ampliar DOTS. Es un alcance de desarrollo: **no reemplaza módulos existentes, no redefine sus resultados y no constituye una auditoría ni una certificación**. Cada elemento se agrega como módulo, capa, herramienta o informe independiente, conectado al DOTS actual mediante accesos adicionales.

### 1. Agricultura, cultivos y agricultura de precisión

- Series temporales de índices de vegetación: NDVI, EVI y SAVI.
- Integración de imágenes Sentinel-2 y Landsat para observación óptica, y Sentinel-1 para radar.
- Seguimiento de cobertura y uso del suelo, evolución de lotes, rotaciones e historia de cultivos.
- Identificación y seguimiento de áreas agrícolas y comparación entre campañas.
- Capas de vigor, estrés y variabilidad intralote, diferenciando observaciones satelitales de índices derivados.
- Módulo de agricultura de precisión con análisis por lote, ambiente y región.
- Pasturas y recursos forrajeros: evolución de cobertura, disponibilidad estimada, productividad y relación con la carga animal.
- Atlas agrícola histórico y comparado, con series documentales y estadísticas disponibles. La referencia temporal de hasta 5.000 años se utilizará únicamente cuando existan registros paleoclimáticos, arqueológicos o reconstrucciones científicas pertinentes; cada período deberá identificarse como registro, reconstrucción o estimación, sin presentar reconstrucciones como observaciones directas.

### 2. Ganadería, visión artificial e identificación animal

- Detección de bovinos y otros animales en imágenes y videos.
- Conteo automático por cuadro, lote, corral, cámara y período.
- Seguimiento de desplazamientos, entradas y salidas, permanencia y distribución espacial.
- Identificación de animales individuales mediante lectura de caravanas visuales, RFID u otros identificadores disponibles.
- Vinculación de la identidad entre cámaras y fechas sólo mediante un identificador persistente verificable; los IDs temporales de seguimiento no se considerarán identidad individual.
- Registro de rodeos, categorías, cantidad de animales, densidad y ocupación de corrales.
- Relación espacial entre animales, aguadas, sombra, comederos y superficie de pastoreo.
- Herramientas para analizar disponibilidad forrajera, carga animal y distribución del pastoreo.
- Indicadores de estrés térmico y condiciones ambientales asociados a datos meteorológicos y registros disponibles.
- Historial por animal y por rodeo cuando exista identificación trazable.

### 3. Suelos y aptitud productiva

- Capas de textura, proporción de arcilla, limo y arena.
- Materia orgánica, carbono y nitrógeno.
- Humedad, cobertura, degradación y evolución de las condiciones del suelo.
- Densidad aparente, resistencia a la penetración y compactación.
- Infiltración, drenaje, profundidad efectiva y condiciones para el desarrollo radicular.
- Comparación entre información satelital, productos modelados y análisis de laboratorio o mediciones georreferenciadas.
- Ficha de suelo por lote, perfiles por profundidad y evolución temporal.
- Mapas de limitaciones y aptitud productiva, con variables, unidades, profundidad y procedencia visibles.
- Incorporación de observaciones de campo para calibrar o complementar los productos de suelo.

### 4. Territorio, relieve y visualización 3D

- Visor tridimensional de terreno y elevación para lotes, departamentos, provincias, regiones y cuencas.
- Modelos digitales de elevación, sombreado, pendientes, orientación y perfiles topográficos.
- Delimitación y visualización de cuencas, subcuencas, divisorias y redes de drenaje.
- Superposición de imágenes satelitales, uso del suelo, vegetación, agua, suelos e infraestructura.
- Navegación desde escala regional hasta lote, conservando la referencia geográfica.
- Herramientas para seleccionar áreas, medir distancias y superficies, consultar perfiles y comparar capas.
- Visualización de exposición territorial de establecimientos, infraestructura y población frente a amenazas ambientales.
- El visor 3D se incorpora como capacidad adicional y no sustituye el visor geográfico que DOTS ya utiliza.

### 5. Hidrología, cuencas e inundaciones

- Seguimiento de las cuencas de los ríos Paraná, Iguazú, Uruguay, Paraguay, Bermejo y Pilcomayo, además de las cuencas y regiones relacionadas de Argentina, Brasil, Uruguay y Bolivia.
- Consulta de niveles, caudales, estaciones y registros hidrométricos disponibles.
- Capas de red hidrográfica, acumulación de flujo, drenaje y áreas susceptibles a anegamiento.
- Integración de MERIT Hydro, GloFAS, Copernicus, INA y otras fuentes oficiales pertinentes.
- Detección y seguimiento de agua e inundaciones observadas mediante Sentinel-1 y productos satelitales.
- Consulta histórica de eventos, niveles y extensión de áreas afectadas cuando existan series disponibles.
- Análisis territorial de población, establecimientos, caminos e infraestructura expuestos.
- Escenarios de inundación como módulo diferenciado, con parámetros y modelo hidrológico/hidráulico identificados; no confundirlos con mapas de agua observada.

### 6. Clima, variabilidad y riesgos agroambientales

- Seguimiento de El Niño, La Niña y ENSO, con indicadores oceánicos y atmosféricos.
- Series de precipitación, temperatura, humedad y variables meteorológicas.
- Integración de ERA5, CHIRPS, NASA POWER, ECMWF y fuentes oficiales nacionales.
- Análisis de sequías, excesos hídricos, heladas, olas de calor y condiciones de estrés agropecuario.
- Pronósticos y perspectivas estacionales presentados por separado de los registros observados.
- Series históricas de 20 a 30 años cuando la cobertura y calidad de las fuentes lo permitan.
- Alertas de incendios y focos de calor con fuentes como MODIS y VIIRS.
- Comparación entre regiones, campañas agrícolas y períodos climáticos.

### 7. Población, infraestructura y exposición territorial

- Capas de población y distribución territorial para contextualizar los riesgos agroambientales.
- Integración de WorldPop y fuentes censales oficiales disponibles.
- Cruce espacial de población, establecimientos productivos, infraestructura, redes viales, cursos de agua y áreas expuestas.
- Indicadores territoriales por cuenca, municipio, provincia y región.
- Diferenciación entre población censada, estimaciones gridded y resultados derivados de cruces geoespaciales.

### 8. Informes, series y productos de salida

- Generación de informes PDF por lote, establecimiento, municipio, provincia, región o cuenca.
- Informes con mapas, vistas 3D cuando correspondan, gráficos, tablas, series históricas y comparaciones.
- Exportación de datos y tablas en CSV.
- Fichas específicas de agricultura, ganadería, suelos, clima, hidrología y exposición territorial.
- Inclusión de fuentes, fecha, unidad, escala espacial, período, metodología y versión de procesamiento en cada producto.
- Separación explícita entre observación, dato administrativo, producto satelital, estimación, pronóstico y escenario.
- Presentación de datos faltantes como faltantes, sin completar valores ni generar cifras ficticias.

### 9. Organización de la ampliación

Los ítems anteriores se incorporan como módulos funcionales nuevos dentro de DOTS, con sus propias vistas, servicios, capas y herramientas. Los módulos existentes permanecen como están. La navegación puede sumar nuevas entradas y agrupaciones, pero no eliminar, renombrar ni sustituir accesos actuales. Las conexiones con fuentes externas se agregan sin duplicar ni alterar conectores ya presentes.

