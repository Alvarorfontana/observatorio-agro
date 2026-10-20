# DOTS Campo — laboratorio ambiental: primera entrega
Se añade un contrato TypeScript compartido para cuatro módulos: inundaciones, vegetación, sequía e incendios.
Archivo: `src/lib/environmentalTimeline.ts`.

**Importante:** esto NO activa capas en producción ni consulta servicios externos. Los fotogramas solo se reproducirán cuando existan observaciones válidas, georreferenciadas y autorizadas. `kind` separa observado, pronóstico y escenario; nunca presentar interpolaciones visuales como mediciones. `makeTimeline` descarta metadatos inválidos y ordena adquisiciones reales.

Siguiente integración: localizar el componente Leaflet actual; crear panel temporal y renderizador GeoJSON/GeoTIFF, con leyenda y metadatos; enlazar al backend GFM/INA y verificar Bella Vista. Los mapas base de alta resolución requieren proveedor/licencia/atribución y disponibilidad verificadas. Validar `npm run build` antes de fusionar.
