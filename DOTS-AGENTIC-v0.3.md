# DOTS Agentic v0.3

- Informe Agentic en panel amplio sobre el mapa.
- PDF técnico descargable reutilizando el análisis ya calculado (evita duplicar llamadas a APIs).
- Consultas de dominio paralelas: una fuente lenta/caída no bloquea el informe completo.
- Inventario operativo en `/api/fuentes/agentic/status`.
- Trazabilidad por fuente y estados recibido/sin dato.
- Se mantienen como pendientes explícitos: NDVI/EVI raster, biomasa, bebederos e inventario/sensores de ganado.
- NASA FIRMS requiere `FIRMS_MAP_KEY` en Vercel para datos de focos/incendios.
