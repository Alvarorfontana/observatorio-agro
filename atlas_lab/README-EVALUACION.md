# Evaluador reproducible de manchas de agua

## Alcance

Este evaluador compara una máscara de detección con una máscara de referencia **independiente**. No descarga escenas, no crea verdad-terreno, no modifica el detector Sentinel-1 y no convierte una detección en una inundación confirmada.

## Requisitos opcionales

Instalar en el entorno de análisis, sin añadirlos a las dependencias obligatorias de DOTS:

```bash
python -m pip install numpy rasterio pytest
```

## Preparación de los datos

1. Exportar la detección como GeoTIFF binario: valores mayores que cero = agua detectada; cero = no detectado.
2. Preparar una máscara independiente alineada: `1` = agua, `0` = no agua, `255` = incierto/no evaluar.
3. Ambos archivos deben tener idénticas dimensiones, CRS y transformación affine. El programa rechaza archivos desalineados; no los reproyecta silenciosamente.
4. La referencia debe documentar fuente, fecha, intérprete, escala, confianza y método. No usar la misma escena Sentinel-1 que alimentó al detector como única referencia.
5. Mantener separados los eventos usados para ajustar parámetros y los eventos usados para evaluar.

## Ejecución

Desde la raíz del repositorio:

```bash
python atlas_lab/evaluar_manchas_agua.py \
  --prediction datos/evento_01_deteccion.tif \
  --reference datos/evento_01_referencia_independiente.tif \
  --event-id corrientes_evento_01 \
  --output resultados/evento_01_metricas.json
```

El JSON registra matriz de confusión, precision, recall, F1, IoU, Dice, cobertura válida y error de superficie cuando el CRS está proyectado en metros. Si no puede calcular superficie con seguridad, lo informa y omite esa métrica.

## Pruebas

```bash
pytest -q tests/test_evaluar_manchas_agua.py
```

Las pruebas verifican el cálculo matemático con arrays sintéticos. **No son validación geográfica ni validación del detector.**

## Protocolo mínimo por evento

- Identificador, fecha/hora y zona.
- IDs STAC/escenas y parámetros del algoritmo.
- Fuente independiente de referencia y licencia.
- Cobertura válida y áreas excluidas.
- Métricas y matriz de confusión.
- Revisión de falsos positivos/negativos por cobertura (agua abierta, vegetación, suelo agrícola, urbano).
- Versión de código y checksums de entradas/salidas.

No publicar alertas ni calificar las manchas como inundación confirmada hasta completar evaluación independiente y revisión científica.
