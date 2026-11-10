# DOTS — Estándar de redacción e interpretación de informes

## 1. Propósito editorial

Los informes de DOTS deben ser documentos técnicos interpretativos, no listados de valores ni galerías de mapas. El lector debe comprender qué se observó, dónde, cuándo, mediante qué instrumento, qué significa agronómica o territorialmente y qué decisiones merece considerar.

La redacción será precisa, sobria, comprensible para productores, asesores y responsables de establecimientos. Evitar jerga sin explicación, adjetivos promocionales, conclusiones categóricas no demostradas y recomendaciones genéricas.

## 2. Regla central: dato, interpretación, alcance y acción

Cada hallazgo relevante debe contener, en este orden:

1. **Observación:** valor, unidad, fecha, superficie/ubicación y fuente.
2. **Interpretación:** significado del valor en el contexto del lote, cultivo, estación, serie temporal o variable relacionada.
3. **Alcance y confianza:** resolución espacial/temporal, cobertura, calidad, nubosidad, tamaño de muestra, método, incertidumbre y limitaciones.
4. **Implicancia práctica:** qué conviene verificar o considerar en la gestión del establecimiento.
5. **Verificación:** qué recorrida, medición, análisis de laboratorio, registro productivo o instrumento permitiría confirmar la hipótesis.

No convertir correlaciones en causas ni indicadores indirectos en mediciones directas.

## 3. Estructura narrativa recomendada

### Síntesis ejecutiva
- Identificación del establecimiento y lote, superficie delimitada, coordenadas o referencia geográfica.
- Período analizado, fecha de corte y fecha de generación.
- Fuentes efectivamente consultadas y cantidad de observaciones válidas.
- Tres a cinco hallazgos principales, cada uno con evidencia y grado de confianza.
- Limitaciones relevantes y prioridades de verificación a campo.

### 1. Caracterización del lote
Describir geometría, superficie calculada, ubicación, relieve y contexto de cobertura. Aclarar si el límite fue dibujado por el usuario o provino de una fuente oficial. No inferir titularidad ni uso legal.

### 2. Observación satelital
Mostrar imagen real del lote, sensor, producto, fecha de adquisición, resolución, porcentaje de píxeles válidos/nubosidad cuando esté disponible, máscara aplicada y extensión espacial. Distinguir la imagen de contexto de los productos analíticos.

### 3. Estado de la vegetación
Interpretar NDVI/EVI/SAVI/NDMI según el índice, la fecha, la cobertura y la etapa fenológica conocida o estimada. Incluir mapa recortado al lote, distribución de valores, estadísticos zonales y evolución. No aplicar umbrales universales de vigor como diagnóstico de cultivo o rendimiento.

### 4. Ambientes y variabilidad intralote
Explicar cómo se calcularon las zonas (por ejemplo, agrupamiento estadístico de píxeles válidos), qué porcentaje y hectáreas representa cada clase, y qué significa la variabilidad observada. Las zonas son clases relativas de la escena y no categorías agronómicas definitivas hasta su validación.

### 5. Evolución y comparación de campañas
Comparar fechas o campañas equivalentes, usando la misma fuente, resolución, máscara, geometría y metodología cuando sea posible. Indicar si la diferencia puede deberse a fenología, rotación, manejo, suelo, clima, nubosidad residual o diferencias de sensor. No comparar directamente valores de productos incompatibles sin advertencia.

### 6. Agua, clima y relieve
Separar mediciones observadas, estimaciones, pronósticos y modelos. Indicar período, unidad, resolución y distancia/representatividad de estaciones o celdas de grilla. El balance hídrico modelado no equivale a humedad medida en cada punto del lote.

### 7. Suelos y aptitud
Aclarar escala y naturaleza de cada fuente. SoilGrids y cartografía regional son estimaciones/modelos de referencia; no reemplazan análisis de laboratorio ni calicatas. Las inferencias sobre drenaje, erosión, compactación o fertilidad deben expresarse como indicios a verificar.

### 8. Implicancias y plan de verificación
Proponer verificaciones concretas, priorizadas y proporcionales a la evidencia. No indicar dosis de fertilizantes, agroquímicos, densidades de siembra ni pronósticos de rendimiento sin datos locales suficientes, calibración y validación profesional.

### Anexo metodológico y trazabilidad
Incluir fuentes, identificadores de escena/producto, fechas, resolución, CRS, geometría usada, filtros, fórmulas, versión del procesamiento, datos faltantes y advertencias. Incluir tablas completas y diccionario de indicadores cuando aporte valor.

## 4. Lenguaje y calibración de afirmaciones

Usar formulaciones calibradas:
- **Observado:** “La escena Sentinel-2 del [fecha] registra…”
- **Calculado:** “El promedio zonal de NDVI calculado sobre los píxeles válidos fue…”
- **Estimado:** “El producto/modelo estima… a la escala de…”
- **Indicio:** “La distribución espacial es compatible con…, pero no permite confirmar…”
- **Hipótesis:** “Una explicación posible, que requiere verificación, es…”
- **Sin evidencia suficiente:** “Con los datos disponibles no es posible determinar…”

Evitar “el lote está sano”, “el cultivo rendirá…”, “hay sequía en todo el lote”, “el suelo tiene…” o “la causa es…” cuando el dato sólo es un proxy o modelo.

No llamar “medición” a un valor modelado. No llamar “foto actual” a una imagen cuya fecha de adquisición es anterior. No presentar un mapa de color como medición de campo.

## 5. Reglas específicas para índices y sensores

### NDVI y otros índices
- Definir el índice y sus bandas/fórmula en el anexo.
- Explicar que NDVI mide contraste espectral asociado a vegetación verde, no rendimiento ni salud directamente.
- Interpretar según cultivo, cobertura, suelo expuesto, fenología, saturación, agua/sombra y calidad de píxel.
- Informar fecha y resolución. Sentinel-2 y MODIS no son intercambiables: MODIS a 250 m sirve para tendencias regionales/históricas y puede mezclar coberturas en lotes pequeños; Sentinel-2 a 10 m permite mayor detalle espacial cuando hay escena válida.
- No promediar píxeles inválidos ni ocultar la proporción descartada.
- Las clases de vigor deben describirse como relativas a la escena/lote y al método aplicado.

### Radar y agua
- Sentinel-1 observa retrodispersión radar; la interpretación depende de humedad, rugosidad, estructura, geometría de observación y cobertura. No afirmar anegamiento sin corroboración suficiente.
- Los pronósticos de caudal GloFAS son valores modelados en una celda hidrológica; no son nivel del río ni mapa de inundación parcelaria.

### Suelos, clima y producción
- Distinguir sensor, estación, grilla, reanálisis, modelo y dato declarado por el productor.
- Rendimientos, márgenes, costos y consumo de insumos sólo se calculan con registros reales y metodología explícita.
- No completar huecos con valores ficticios o promedios no declarados.

## 6. Calidad, confianza y datos faltantes

Cada resultado debe exponer:
- Estado: recibido, parcial, sin dato o error.
- Fuente y producto.
- Fecha de adquisición/observación y fecha de procesamiento.
- Resolución espacial y temporal.
- Cobertura válida, nubosidad o calidad cuando exista.
- Método y versión.
- Limitaciones relevantes.

Usar confianza cualitativa (alta, media, baja) sólo si existen criterios explícitos documentados. No inventar un porcentaje de confianza. La ausencia de datos debe aparecer como “sin dato” y nunca como cero.

## 7. Mapas y gráficos

- El lote real es el elemento central: imagen de contexto y capas analíticas alineadas sobre la misma geometría.
- Cada mapa debe llevar título interpretativo, leyenda, unidades, fecha, sensor, resolución, fuente y escala.
- Curvas temporales deben mostrar fechas, cantidad de observaciones y huecos. Comparaciones deben mantener escalas equivalentes o explicar el cambio.
- Los mapas de zonas deben mostrar superficie y porcentaje por clase, método y fecha.
- La interpretación escrita debe referenciar elementos visibles del mapa: sectores, bordes, bajos, lomas o polígonos sólo cuando estén identificados por la geometría/datos; no inventar topónimos ni rasgos.
- No usar gráficos decorativos ni imágenes generadas para aparentar observaciones satelitales reales.

## 8. Ejemplo de redacción aceptable

“En la escena Sentinel-2 L2A adquirida el [fecha], el NDVI medio calculado para los píxeles válidos del polígono fue [valor], con [porcentaje]% de cobertura válida. La distribución espacial presenta valores relativamente menores en [sector identificado en el mapa] y mayores en [sector], según la clasificación estadística aplicada a esta escena. Esta diferencia describe variabilidad espectral intralote en esa fecha; por sí sola no identifica su causa ni permite estimar rendimiento. Conviene contrastarla con la etapa del cultivo, el historial de manejo y una recorrida dirigida a ambos sectores.”

Los campos entre corchetes deben completarse exclusivamente con resultados reales; si no existen, se omiten o se declara “sin dato”. Este ejemplo es una plantilla, no un resultado observado.

## 9. Control editorial antes de emitir el PDF

- ¿Cada cifra tiene unidad, fecha, fuente y escala?
- ¿Se distingue observado, calculado, estimado, pronosticado e informado por el usuario?
- ¿La interpretación está respaldada por el dato y su contexto?
- ¿Se explicitan las limitaciones que cambian la conclusión?
- ¿Los mapas corresponden al lote y a la escena citada?
- ¿Las comparaciones son metodológicamente compatibles?
- ¿Se identifican vacíos, errores y cobertura insuficiente?
- ¿Las recomendaciones son verificables y no exceden la evidencia?
- ¿Se evitaron causalidades, rendimientos o diagnósticos no validados?

Un informe que no supera estos controles no debe emitir conclusiones firmes; debe presentar los resultados como preliminares o parciales.
