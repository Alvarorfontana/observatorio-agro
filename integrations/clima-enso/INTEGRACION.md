# Integración del motor científico Clima ENSO v4

El motor fuente fue entregado en `clima-enso-pack-v4.zip`. El 20/10/2026 se ejecutaron localmente sus pruebas originales en Python: **31 passed** (1,37 s). Esa ejecución no prueba por sí sola la disponibilidad de fuentes remotas.

## Incorporación reproducible

1. Descargar el archivo ZIP original al equipo donde se clonó este repositorio.
2. Desde la raíz del repositorio, en la rama `integracion-clima-enso-v4`, ejecutar:

   ```bash
   python3 tools/import_clima_enso_pack.py /ruta/clima-enso-pack-v4.zip
   python3 -m venv .venv-enso
   . .venv-enso/bin/activate
   python -m pip install -e integrations/clima-enso-analyzer
   python -m pytest -q integrations/clima-enso-analyzer/tests
   ```

3. Revisar cambios, licencias y dependencias antes del commit. **No incluir** `datos/`, `data_cache/`, `.nc`, dashboards HTML ni resultados sintéticos.
4. El workflow `.github/workflows/enso-validation.yml` valida los adaptadores y ejecuta la suite del motor cuando esté incorporado.

## Fuentes y etiquetas de evidencia

- `/api/enso/oni`: NOAA CPC, observación oficial trimestral.
- `/api/enso/nino-regions`: NOAA CPC, anomalías SST mensuales.
- `/api/enso/soi`: NOAA PSL, índice SOI mensual.
- `/api/enso/scientific-report`: análisis descriptivo derivado de ONI observado, **no** predicción.
- `/api/enso/iri`: catálogo oficial IRI, **sin** ingestión numérica de pronósticos todavía.

**Pendiente**: importar efectivamente el motor en esta rama, ejecutar la CI con todas las dependencias, validar respuestas HTTP en producción y desarrollar un conector numérico IRI sobre un formato estable verificable. El motor importado no debe formar parte del build web ni activarse automáticamente hasta superar las pruebas.
