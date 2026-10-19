# Integración progresiva de radares e hidrología — DOTS Campo

Rama de trabajo: `mejora-auditoria-fuentes-20261019`. Producción y `main` sin cambios.

## Implementado en esta rama

- `flood_sar_change.py`: comparación de dos escenas SAR VV *ya alineadas*, clasificación de agua libre, hectáreas nuevas/persistentes/retiradas y cobertura válida.
- `tests/test_flood_sar_change.py`: pruebas de umbral, ausencia de datos, grillas incompatibles y bloqueo de alertas automáticas.
- `scripts/audit_hydro_radar.py` y `tests/test_audit_hydro_radar.py`: auditoría offline y pruebas de seguridad.
- `docs/MATRIZ-FUENTES-HIDROLOGICAS.md`: inventario regional.

## Integraciones pendientes — no declarar como operativas

1. **Sentinel-1 / Microsoft Planetary Computer**: adaptar `radar.py` para obtener dos escenas coregistradas con geometría, resolución y órbita comparables; extraer valores VV reales y aplicar el nuevo núcleo. La API de estadísticas agregadas actual no entrega por sí sola el mapa de transición píxel a píxel.
2. **Copernicus GFM**: contrastar la máscara de agua nueva con `gfm.py`, cuidando fecha de pasada y agua permanente.
3. **HYDRAFloods, SERVIR y UN-SPIDER**: evaluar métodos, licencia, dependencias y reproducibilidad antes de adaptar algoritmos. No se ha importado código de terceros.
4. **PySheds, RichDEM, HydroMT**: ejecutar delineación y relieve fuera del servidor web; verificar DEM, proyección y calidad.
5. **GEOGLOWS/GloFAS + INA/organismos regionales**: calibrar resultados satelitales con series observadas, sin confundir caudal pronosticado con nivel medido.
6. **Random Forest**: entrenar solamente con etiquetas de inundación verificadas, separación temporal/espacial de entrenamiento y validación y métricas de falsos positivos.

## Validación mínima para publicar

- Ejecutar `python -m pytest tests/test_flood_sar_change.py tests/test_audit_hydro_radar.py -q`.
- Comparar escenas de igual geometría y polarización; registrar fechas y órbita.
- Evaluar errores frente a máscaras de referencia independientes y terreno.
- Medir cobertura, latencia y costo de procesamiento.
- Documentar licencias y atribución de cada fuente.
- Revisar los resultados antes de fusionar a `main`.

**Importante:** este núcleo es una estimación experimental de agua libre. No mide profundidad, no detecta de manera confiable vegetación inundada y no constituye una alerta oficial.
