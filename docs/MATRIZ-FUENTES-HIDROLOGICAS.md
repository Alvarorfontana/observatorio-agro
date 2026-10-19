# DOTS Campo — matriz de integración hidrológica regional

**Estado:** inventario de ingeniería; no certifica acceso en tiempo real ni operación en producción.

| País | Organismo o fuente | Dato prioritario | Estado verificado en código | Próxima comprobación |
| --- | --- | --- | --- | --- |
| Argentina | INA / API A5 | Altura y caudal observados | Conector `ina_a5.py` presente | Probar estaciones, fecha, unidades y umbrales |
| Brasil | ANA / HidroWeb, ONS | Estaciones y represas | ONS mencionado e implementado en `cuenca.py`; ANA no certificada aquí | Revisar rutas reales, identificadores y licencia |
| Paraguay | DMH | Niveles y lluvia | Referencias en documentación y panel | Localizar endpoint abierto, cobertura y periodicidad |
| Uruguay | DINAGUA / INUMET | Niveles y precipitación | Referencias en documentación y panel | Validar APIs públicas, series y unidades |
| Bolivia | SENAMHI | Lluvia y niveles de cabecera | Referencias en documentación y panel | Verificar disponibilidad de datos descargables |
| Regional | Open-Meteo Flood / GloFAS | Pronóstico de caudales | `cuenca.py` | Comparar con observaciones y fechas de emisión |
| Regional | Copernicus GFM / Sentinel-1 | Extensión observada de inundación | `gfm.py` y `radar.py` | Comprobar cobertura espacial, fechas y máscaras |
| Regional | CHIRPS | Precipitación histórica | `rainfall.py` | Comprobar API, demora de publicación y series completas |

## Reglas antes de integrar repositorios externos

1. Reutilizar conectores existentes; evitar introducir un segundo motor de mapas o radar.
2. Mantener separadas observación oficial, pronóstico, estimación satelital y análisis experimental.
3. No mostrar como **operativa** una fuente solamente porque exista URL, módulo o credencial.
4. Registrar fecha de observación, fecha de consulta, organismo, unidad, cobertura y límites.
5. Aislar bibliotecas geoespaciales pesadas en procesos offline (por ejemplo, GitHub Actions).
6. No desplegar ni fusionar a `main` hasta ejecutar pruebas y validar respuestas reales.
7. No incorporar claves, tokens ni datos sensibles al repositorio.

## Próximos hitos verificables

- Ejecutar `python -m pytest tests/test_audit_hydro_radar.py -q`.
- Ejecutar `python scripts/audit_hydro_radar.py` y, en entorno con red, `--live`.
- Inspeccionar respuestas de ANA, DMH, DINAGUA/INUMET y SENAMHI antes de escribir conectores.
- Definir pruebas de frescura (edad máxima), valores ausentes y unidades para cada fuente.
- Preparar una solicitud de incorporación a `main` solo después de revisar los resultados.
