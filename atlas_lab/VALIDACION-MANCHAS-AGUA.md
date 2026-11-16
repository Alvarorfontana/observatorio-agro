# Validación científica — detección de manchas de agua

## Qué existe

El repositorio contiene:
- `scripts/anegamientos.py`: pipeline de escenas Sentinel-1 RTC de Microsoft Planetary Computer, selección de órbita, filtrado Lee, fondo temporal, detección de cambio, polígonos y exportación JSON/GeoJSON.
- `scripts/manchas_agua.py`: algoritmos de speckle, umbral, agrupamiento y control temporal.
- `tests/test_manchas_agua.py`: pruebas sintéticas del filtro, umbral, manchas, área, Hampel y cadena completa simulada.

Las pruebas sintéticas verifican comportamiento del código, no demuestran que el método identifique correctamente inundaciones reales en Corrientes. El propio pipeline declara que el producto es orientativo y no está validado en terreno.

## Objetivo de la validación

Estimar sensibilidad, precisión, tasa de falsas alarmas y error de superficie de las detecciones de agua nueva, diferenciando:
- agua permanente;
- agua estacional habitual;
- inundación nueva;
- suelo húmedo o saturado;
- sombras radar, ruido y artefactos;
- vegetación inundada y agua bajo dosel (limitación de C-band);
- cambios por cultivo, laboreo o humedad del suelo.

## Diseño del piloto

### A. Zonas y eventos

1. Empezar por Goya, Esquina, Santa Lucía, Bella Vista, Corrientes capital, Ituzaingó y Paso de los Libres.
2. Seleccionar al menos tres eventos de crecida/inundación con fechas conocidas y al menos dos períodos sin inundación.
3. Mantener una zona de control sin evento.
4. Documentar órbita relativa, dirección, fecha/hora, polarización, incidencia, cobertura y número de escenas usadas en el fondo.
5. Evitar comparar pasadas de geometrías distintas como si fueran equivalentes.

### B. Referencias independientes

Prioridad de referencia:
1. Imágenes ópticas Sentinel-2/Landsat cercanas a la fecha, solo cuando la nubosidad permita interpretación.
2. Registros de altura/caudal de estaciones INA cercanas, como evidencia hidrológica contextual, no como verdad-terreno de cada píxel.
3. Cartografía y reportes oficiales de emergencias con fecha y área.
4. Fotografías georreferenciadas o relevamientos de campo con fecha, si existen.
5. Productos independientes de extensión de inundación, registrando resolución y método.

No usar el mismo producto Sentinel-1 que genera la detección como única referencia para validarla.

### C. Muestra y etiquetado

- Crear polígonos de referencia por evento: agua, no agua, agua permanente, incierto.
- Etiquetar a ciegas respecto del resultado del algoritmo cuando sea posible.
- Registrar intérprete, fuente, fecha, escala y confianza.
- Excluir o marcar como inciertas áreas con referencia insuficiente.
- Separar los datos de calibración de los de evaluación; no ajustar y evaluar sobre las mismas fechas o polígonos.

### D. Métricas

Calcular por evento y agregadas:
- Matriz de confusión a nivel píxel y objeto.
- Precisión (precision), exhaustividad (recall) y F1.
- IoU/Jaccard y Dice para polígonos.
- Error absoluto y relativo de superficie inundada.
- Tasa de falsas alarmas por zona y por fecha.
- Porcentaje de área sin cobertura válida.
- Latencia entre adquisición y producto.

Informar intervalos de confianza y resultados por tipo de cobertura (agua abierta, vegetación, suelo agrícola, urbano).

## Criterios de publicación propuestos

Estos son umbrales iniciales de aceptación del piloto, no resultados ya obtenidos:
- F1 ≥ 0,80 en agua abierta con referencia independiente.
- IoU ≥ 0,65 para polígonos de agua nueva.
- Error absoluto de superficie ≤ 25% en eventos con cobertura suficiente.
- Cobertura válida ≥ 80% del área de estudio.
- Publicar falsas alarmas y casos fallidos, no solo ejemplos exitosos.

Si no se alcanzan los umbrales, clasificar el producto como experimental, ajustar el método y repetir con un conjunto de evaluación separado.

## Controles técnicos antes de validar

- Verificar unidades de backscatter y conversión lineal/dB.
- Revisar calibración radiométrica, terreno, incidencia y máscara de borde.
- Comprobar que el fondo excluya la ventana reciente y no incluya el evento evaluado.
- Medir sensibilidad a los parámetros del filtro Lee, sigma-clipping y área mínima.
- Comprobar estabilidad frente a órbitas y fechas faltantes.
- Guardar versión de código, parámetros, IDs STAC, URLs de activos y checksum de cada salida.
- Asegurar que el GeoJSON use CRS WGS84 y geometrías válidas.

## Estado y siguiente paso

**Estado actual: experimental; no validado en terreno.**

Las pruebas sintéticas existentes son útiles y deben conservarse. El siguiente paso es ejecutar el pipeline en las zonas piloto, archivar escenas y metadatos, seleccionar eventos históricos con referencias independientes y calcular las métricas anteriores. No activar alertas públicas ni describir las manchas como inundaciones confirmadas hasta completar esa evaluación.
