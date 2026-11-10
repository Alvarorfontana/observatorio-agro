# DOTS — Arquitectura de Agricultura de Precisión

**Estado:** arquitectura técnica para implementación incremental.  
**Rama:** `feat/dots-vision-suelos-territorio`  
**Restricción económica:** etapa de desarrollo y pruebas con presupuesto cero. No incorporar servicios que requieran suscripción, instancia paga, GPU contratada ni consumo facturable.  
**Regla de preservación:** ampliación aditiva. No eliminar, sustituir ni cambiar el comportamiento de módulos, rutas, conectores o capas existentes.

## 1. Objetivo funcional

Construir un módulo de Agricultura de Precisión por lote que reúna observación satelital, series temporales, índices espectrales, zonificación de ambientes, contexto climático e información de suelo. El módulo debe permitir pasar de una vista regional a un lote dibujado o recuperado del inventario, conservar su geometría y producir resultados trazables.

No debe convertir un índice de vegetación en una recomendación agronómica automática. Las recomendaciones de manejo se habilitan sólo cuando existan cultivo, campaña, etapa fenológica, datos de campo y reglas agronómicas documentadas.

## 2. Arquitectura lógica

```text
DOTS web (React / Leaflet / ECharts)
  ├─ selector de establecimiento y lote / dibujo GeoJSON
  ├─ mapa de escenas y capas raster
  ├─ series temporales y comparación de campañas
  ├─ zonificación intralote y estadísticas
  └─ ficha de procedencia + exportación
          |
          | HTTPS / JSON / GeoJSON
          v
Flask API existente (/api/fuentes/*)
  ├─ validación de geometría, fechas y parámetros
  ├─ catálogo de fuentes y resolución de disponibilidad
  ├─ adaptadores de observación óptica y radar
  ├─ cálculo zonal y resumen estadístico
  └─ generación de informe y CSV
          |
          +-------------------------------+
          |                               |
          v                               v
Microsoft Planetary Computer          NASA ORNL DAAC
Sentinel-2 L2A / STAC / TiTiler        MODIS MOD13Q1 histórico
sin clave en el flujo actual           servicio público
          |
          +---- fuentes complementarias existentes ----+
               Sentinel-1 / radar, Landsat, SoilGrids,
               clima, humedad, cobertura y forraje
```

El procesamiento inicial es síncrono y bajo demanda, reutilizando los conectores existentes. No se introduce GPU, RunPod, almacenamiento adicional ni un servicio de pago para esta etapa. Si en el futuro una tarea supera los límites razonables de la API, se evaluará primero procesamiento gratuito por lotes; no se migrará automáticamente a infraestructura paga.

## 3. Fuentes y prioridad

| Producto | Fuente prioritaria | Uso y resolución | Condición |
|---|---|---|---|
| Sentinel-2 L2A | Microsoft Planetary Computer STAC/Data API | NDVI, EVI, SAVI, NDMI, NDWI; 10 m para bandas usadas | Público, sujeto a disponibilidad, límites de uso y nubosidad |
| MODIS MOD13Q1 | NASA ORNL DAAC | Serie histórica NDVI, 250 m, compuestos de 16 días | Público; resolución insuficiente para decisiones intralote en lotes pequeños |
| Sentinel-1 | Conectores radar ya presentes en DOTS | Humedad/cambio/agua según producto y algoritmo | No confundir retrodispersión con humedad volumétrica medida |
| Landsat | Catálogo STAC ya disponible | Series de mayor profundidad temporal y resolución de 30 m | Aplicar máscara de nubes y armonización antes de comparar sensores |
| SoilGrids | Conector de suelos existente | Textura, carbono y propiedades modeladas por profundidad | Producto modelado, no análisis de laboratorio del lote |
| Clima | ERA5, CHIRPS, NASA POWER y fuentes ya conectadas | Contexto de precipitación, temperatura y balance | Separar observado, reanálisis, pronóstico y estimación |

**Regla de gratuidad:** no se usarán Earth Engine con facturación, Sentinel Hub con plan pago, openEO con procesamiento contratado ni GPUs alquiladas. Google Earth Engine queda como conector opcional desactivado mientras no se confirme que el proyecto y su modalidad de uso cumplen las condiciones gratuitas aplicables. La ruta de trabajo por defecto es Planetary Computer + NASA ORNL, sin credenciales privadas.

La gratuidad de los proveedores está sujeta a sus términos, cuotas y políticas vigentes. DOTS debe manejar límites y errores sin activar alternativas pagas ni generar cargos.

## 4. Componentes funcionales

### 4.1 Geometría y ficha del lote
- Entrada desde el inventario de lotes o dibujo manual.
- GeoJSON Polygon en WGS84; normalizar y validar anillos, coordenadas, autointersecciones y área.
- Conservar identificador del lote, nombre, establecimiento, campaña y geometría original.
- No usar el centroide como sustituto de la geometría en cálculos zonales.
- Calcular superficie geodésica y mostrarla como estimación geométrica, con unidad ha.

### 4.2 Catálogo y selección de escenas
- Buscar escenas por intersección espacial y ventana temporal.
- Mostrar fecha de adquisición, sensor, identificador de escena, nubosidad declarada, porcentaje despejado medido dentro del lote y cobertura de la huella.
- Elegir como máximo una observación por fecha/sensor para evitar duplicar teselas de una misma pasada.
- Descartar o marcar escenas con nubosidad, nieve, sombra o cobertura insuficiente según máscara y umbrales documentados.
- Si no hay escena válida, devolver «sin dato» y explicar el motivo.

### 4.3 Índices espectrales
- NDVI: `(NIR - Red) / (NIR + Red)`.
- EVI: fórmula estándar con bandas y reflectancias documentadas.
- SAVI: factor L explícito; valor inicial L=0,5 sólo como configuración declarada.
- NDMI: humedad relativa del dosel mediante NIR y SWIR.
- NDWI: índice definido y rotulado sin confundirlo con NDMI; indicar qué variante se utiliza.
- Registrar fórmula, bandas, escala radiométrica, baseline de procesamiento, máscara, fecha y sensor.
- No comparar valores de sensores distintos sin armonización y advertencia.

### 4.4 Series temporales y campañas
- Series Sentinel-2 recientes por lote con estadísticos zonales.
- Serie MODIS histórica como contexto regional/histórico, nunca como resolución parcelaria de 10 m.
- Filtros por período, campaña y cultivo.
- Estadísticos por fecha: media, mediana, percentiles 2/98, desviación estándar, píxeles válidos y fracción despejada.
- Tendencia calculada sólo sobre observaciones válidas; no interpolar vacíos como si fueran observaciones.
- Comparación interanual únicamente con ventanas fenológicas equivalentes cuando se conozcan fechas de siembra y cultivo.

### 4.5 Zonificación de ambientes
- Crear zonas relativas a partir de píxeles válidos de una escena o compuesto temporal.
- Registrar método, número de clases, cortes, muestra de píxeles y escena de origen.
- Distinguir «zonas de vigor relativo» de ambientes agronómicos permanentes.
- Para ambientes estables, exigir varias fechas/campañas y evidencia de campo.
- No etiquetar zonas como fertilidad, rendimiento o dosis variable sin datos que lo respalden.

### 4.6 Integración agronómica
- Relacionar índices con cultivo, campaña, fecha de siembra, etapa fenológica, lluvia, temperatura, humedad y suelo sólo cuando esos datos estén disponibles.
- Forraje y carga animal se presentan en módulos relacionados, con sus propios métodos y limitaciones.
- Rendimiento de cosecha se calcula sólo desde monitor de rendimiento o modelo explícito validado; NDVI no es rendimiento medido.
- Alertas por anomalías son señales para inspección, no diagnósticos de plagas, enfermedades o deficiencias nutricionales.

## 5. Contratos de API existentes a reutilizar

El backend ya expone el prefijo `/api/fuentes` y el registro `VEGETATION` incluye:
- `GET /api/fuentes/ndvi?polygon=...&days=120&scenes=6`
- `GET /api/fuentes/ndvi-modis?polygon=...&days=...`
- `GET /api/fuentes/ndvi-zonas?polygon=...&days=...`
- `GET /api/fuentes/indices-espectrales?polygon=...&indices=NDVI,EVI,SAVI&days=...`
- `GET /api/fuentes/gee-ndvi?polygon=...&ndvi_years=...` (opcional; no debe ser la ruta gratuita predeterminada)
- `GET /api/fuentes/ndvi-imagen?polygon=...&item=...` y `GET /api/fuentes/ndvi-zonas-imagen?polygon=...&item=...` para productos raster cuando el identificador de escena sea válido.

La ruta `ndvi` debe ser la opción de detalle parcelario predeterminada (Sentinel-2 L2A 10 m, Planetary Computer). MODIS queda identificado como serie histórica gruesa. Los endpoints de radar, suelo, cobertura, forraje y clima se consumen desde sus módulos existentes, sin duplicar conectores.

Antes de añadir endpoints nuevos, comprobar si la necesidad puede resolverse ampliando el contrato de un servicio existente sin romper clientes. Cualquier nuevo endpoint debe tener esquema, límites, pruebas y estado explícito.

## 6. Contrato común de resultados

Cada respuesta de análisis debe incluir, directamente o dentro del envelope existente:

- `status`: `recibido`, `sin dato`, `requiere credencial`, `pendiente` o `error`.
- `source` / proveedor y URL del catálogo o producto.
- `sensor`, colección y versión del producto.
- `acquired_at` y `processed_at` en ISO 8601 UTC.
- `geometry` o identificador/huella de la geometría analizada.
- `area_ha`, `crs`, `resolution_m`, período y unidad.
- `method`: índice, fórmula, bandas, máscara, umbrales y algoritmo.
- `quality`: cobertura, fracción válida, nube/nieve y número de píxeles.
- `data`: valores y series observadas.
- `limitations`: límites de escala, temporalidad y validez agronómica.
- `software_version` y `processing_version`.

Los campos sin información se representan como `null` o se omiten con una razón; nunca se completan con números inventados.

## 7. Interfaz de usuario

La vista de Agricultura de Precisión debe organizarse en pestañas o paneles:
1. **Lote:** mapa, geometría, superficie, establecimiento y campaña.
2. **Escenas:** catálogo cronológico, sensor, fecha, nube, cobertura y selección.
3. **Vegetación:** NDVI, EVI, SAVI, NDMI y NDWI con leyendas y unidades.
4. **Ambientes:** zonas de vigor relativo, cortes, estadísticas y escena de origen.
5. **Histórico:** series temporales, comparación de campañas y vacíos.
6. **Contexto:** suelo, humedad, lluvia, clima, cobertura y forraje disponibles.
7. **Informe:** PDF/CSV/GeoJSON con metodología, fuentes y advertencias.

La UI debe mostrar siempre qué fuente está respondiendo. No puede presentar una respuesta HTTP exitosa sin valores como «análisis completo» si el contenido está vacío o sólo contiene errores.

## 8. Seguridad, rendimiento y límites

- No colocar claves, tokens ni credenciales en JavaScript, HTML público ni repositorio.
- Validar geometría y tamaño de consulta en servidor.
- Limitar número de escenas y concurrencia; reutilizar caché pública sólo cuando el producto y licencia lo permitan.
- Aplicar timeout y manejo de 429/5xx sin reintentos infinitos.
- Cachear por hash de geometría normalizada + fuente + período + parámetros + versión de método.
- No guardar videos ni material privado en este módulo.
- No introducir Cloudflare R2 en la ruta de agricultura de precisión salvo que se requiera almacenar productos propios; para el primer prototipo no hace falta.
- No crear cuentas ni servicios nuevos para esta etapa.

## 9. Pruebas y criterios de aceptación

### Pruebas automatizadas
- Polígonos válidos, inválidos, cerrados/abiertos, coordenadas fuera de rango y áreas pequeñas.
- Conversión lat/lon a GeoJSON lon/lat.
- Manejo de escena sin cobertura, con nubes, nieve y píxeles insuficientes.
- Fórmulas NDVI/EVI/SAVI/NDMI/NDWI con valores de prueba conocidos.
- Evitar duplicación de teselas de una misma fecha.
- Series vacías, fechas faltantes, valores nulos y orden temporal.
- Contrato de respuesta y procedencia en todos los estados.
- Tests de regresión para los endpoints y pantallas previos.

### Validación de datos
- Elegir un lote de prueba con geometría conocida y escenas reales disponibles.
- Contrastar la geometría y estadísticas zonales con una segunda herramienta GIS.
- Guardar IDs de escena y parámetros para reproducir el resultado.
- Comparar al menos dos fechas despejadas; una sola escena no certifica tendencia.
- Verificar visualmente en escritorio y móvil que el raster coincide con el lote y que la leyenda corresponde al rango mostrado.

### Condiciones para declarar «operativo»
- API real consultada y respuesta con píxeles válidos.
- Procedencia, fechas, resolución y calidad visibles.
- Pruebas automatizadas aprobadas.
- Validación visual de mapa y estadísticas.
- Ninguna regresión de módulos existentes.
- Sin dependencias ni cargos pagos en el flujo de prueba.

## 10. Secuencia de ejecución

1. Reutilizar Sentinel-2 L2A de Planetary Computer y MODIS de NASA ORNL como fuentes gratuitas de prueba.
2. Actualizar la página para que Sentinel-2 sea el análisis parcelario principal y MODIS quede separado como histórico.
3. Reemplazar la consulta predeterminada a Earth Engine por el endpoint Sentinel-2 abierto; dejar GEE como opción secundaria deshabilitada si requiere configuración.
4. Presentar escenas, índices, calidad y zonas en paneles legibles en vez de volcar JSON crudo.
5. Añadir series por campaña y comparación temporal sin rellenar faltantes.
6. Integrar suelo, humedad, clima y forraje reutilizando APIs existentes.
7. Incorporar exportación con metadatos y fuentes.
8. Ejecutar build, tests y no-regresión; publicar resultados del CI. No desplegar a producción desde esta rama.

## 11. Estado al redactar este documento

La página actual ya permite dibujar un polígono y contiene controles para MODIS, Sentinel-2, índices y zonas. El backend de la rama contiene adaptadores de vegetación y el prefijo de API correspondiente. Sin embargo, la pantalla aún utiliza Earth Engine como consulta histórica principal y muestra resultados complementarios como JSON; por tanto, el módulo no debe considerarse terminado ni certificado.

Este documento fija la arquitectura objetivo y el criterio de gratuidad. No afirma que todos los paneles, comparaciones o validaciones descritos estén implementados.
