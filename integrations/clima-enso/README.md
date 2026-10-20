# Integración controlada: Clima ENSO Analyzer v4 → DOTS Campo

Origen: archivo aportado por el propietario `clima-enso-pack-v4.zip` (20-10-2026).
Destino: `Alvarorfontana/observatorio-agro`.

## Verificación del paquete

- ZIP de ~112 MiB comprimidos, 129 entradas y ~169 MB descomprimidos.
- Proyecto Python `repo/clima-enso-analyzer` con `pyproject.toml`, pruebas y módulos.
- Dashboard Plotly HTML autónomo y tres informes PDF.
- NetCDF de NOAA/NCEP y ERSST en `data_cache/`.
- **Advertencia crucial:** el README del paquete indica que los datos incluidos son *sintéticos calibrados*. No deben exponerse como observaciones NOAA oficiales aunque algunos archivos se denominen `oni.csv`, etc.
- Los NetCDF cacheados requieren verificación independiente de procedencia, fecha, metadatos y licencia antes de presentarlos como datos reales.

## Arquitectura propuesta

1. Conservar la web React/Vite y el endpoint oficial `/api/enso/oni` sin cambios.
2. Incorporar el motor Python de análisis en `integrations/clima-enso-analyzer/` en una rama de integración, sin instalar de inmediato dependencias científicas en el build de Vercel.
3. Mantener archivos pesados `.nc`, PDFs y HTML autocontenidos fuera del bundle de producción. Publicar únicamente salidas validadas, versionadas y reducidas (JSON/CSV).
4. Distinguir observación, reanálisis, pronóstico, derivado y **sintético** en todas las visualizaciones e informes.
5. Ejecutar pruebas unitarias y un pipeline de ejemplo sin conexión antes de habilitar ingestión automática.
6. Integrar gráficos de Niño 1+2/3/3.4/4, SOI, OLR, viento, SST y sequía solamente tras validar fuente y período.

## Cómo importar

Ejecutar desde una copia local del repositorio:

```bash
python3 tools/import_clima_enso_pack.py /ruta/clima-enso-pack-v4.zip
```

El importador copia exclusivamente el código fuente y la documentación del paquete Python, no los datos sintéticos ni los grandes binarios. Revisar los cambios antes de confirmarlos con Git.

## Estado

Esta rama prepara la importación. **No representa una integración funcional del motor Python ni una publicación de los datos**.
