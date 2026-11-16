# ATLAS LAB — Centro de investigación aplicada

ATLAS LAB organiza líneas de investigación científica y desarrollo tecnológico sobre la Tierra. No reemplaza DOTS Campo ni los observatorios existentes: reutiliza sus conectores, servicios y datos mediante contratos compartidos.

## Principios

1. **Reutilizar antes de integrar:** auditar módulos, endpoints, cachés y fuentes existentes antes de crear otro conector.
2. **No confundir catálogo con operación:** una fuente listada no se considera conectada hasta verificar respuesta, licencia, cobertura, latencia y actualización.
3. **No inventar datos:** ante ausencia o error de una fuente, devolver estado explícito `sin_dato`; nunca sustituir observaciones por estimaciones sin etiquetarlas.
4. **Trazabilidad científica:** cada resultado debe registrar fuente, producto, fecha de adquisición, período, resolución, método, versión de algoritmo, incertidumbre y validación.
5. **Separación entre dato y modelo:** observaciones, reanálisis, pronósticos, simulaciones y productos derivados deben identificarse por separado.
6. **Arquitectura actual:** conservar Flask/Python para procesamiento y Vite/React para la interfaz existente. No migrar el backend ni duplicar dependencias cartográficas sin una justificación técnica y una prueba de rendimiento.

## Nueve grupos de investigación

| ID | Grupo | Líneas principales | Capacidades DOTS para auditar y reutilizar |
|---|---|---|---|
| G01 | Espectroscopia y Teledetección | Índices multiespectrales, firmas espectrales, agua, vegetación, nieve, minerales y materiales | `spectral_indices.json`, `spectral.py`, Sentinel-2, Landsat, MODIS |
| G02 | Geodesia, LIDAR e Interferometría | Elevación, deformación, desplazamiento, nubes de puntos y modelos 3D | DEM/GeoTIFF, utilidades GIS y geometrías existentes; incorporar InSAR/LIDAR solo con fuentes verificadas |
| G03 | Hidrología y Oceanografía | Agua continental y marina, temperatura, salinidad, sedimentos y dinámica costera | INA A5, Copernicus Marine (si está habilitado), balance hídrico y fuentes satelitales |
| G04 | Clima y Ciencias Atmosféricas | Variables meteorológicas, radiación, aerosoles, gases, extremos y cambio climático | `research_connectors.py`, `climate_indices.py`, `water_balance.py`, ERA5, CHIRPS, NASA POWER, NOAA |
| G05 | Geología y Recursos Minerales | Geomorfología, alteraciones, mineralogía, exploración y cambios de superficie | DEM, Sentinel-2/Landsat y espectros existentes; sumar SEGEMAR y productos hiperespectrales con licencias verificadas |
| G06 | Ciudades e Infraestructura | Islas de calor, expansión urbana, deformación, transporte y exposición | GIS, datos poblacionales, amenazas, térmico satelital y modelos de elevación |
| G07 | Inteligencia Artificial y Modelización | Clasificación, detección de anomalías, modelos físicos, incertidumbre y simulación | Python/Flask, motor Agentic y pipelines existentes; modelos sujetos a evaluación y reproducibilidad |
| G08 | Hidrología Fluvial y Análisis de Cuencas | Niveles, caudales, crecidas, sedimentos, cauces, humedales e inundaciones | `ina_a5.py`, GFM, Sentinel-1, `scripts/anegamientos.py`, `manchas_agua.py`, modelos de relieve |
| G09 | Glaciología, Criósfera y Dinámica del Hielo | Nieve, balance de masa, espesor, velocidad, fusión, lagos glaciares y aporte hídrico | Sentinel-1/2, Landsat, DEM, clima y espectros; incorporar IANIGLA/CONAE, ICESat-2 y GRACE-FO tras verificar productos |

## Núcleo compartido de datos científicos

Cada adaptador debe exponer un envelope compatible con DOTS:

```json
{
  "status": "ok | sin_dato | parcial | error",
  "data": {},
  "error": null,
  "consulted_at": "ISO-8601 UTC",
  "source_url": "URL pública sin credenciales",
  "scope": "área y período consultados",
  "organism": "organismo/productor",
  "provenance": {
    "product": "identificador de producto",
    "acquired_at": "ISO-8601",
    "resolution": "resolución espacial/temporal",
    "method": "método y versión",
    "license": "condiciones de uso",
    "quality_flags": []
  }
}
```

La ampliación de provenance debe ser retrocompatible: no cambiar el significado de los campos que ya consume el frontend.

## Fuentes prioritarias

- **Argentina:** CONAE, IANIGLA-CONICET, INA, SMN, IGN y SEGEMAR.
- **Internacionales:** NASA Earthdata, ESA/Copernicus, USGS, NOAA, NSIDC, ECMWF y productos científicos universitarios.
- Cada fuente requiere ficha de acceso, licencia, atribución, restricciones de redistribución, cobertura, frecuencia de actualización y método de descarga.

## Orden de implementación

1. Inventario de conectores existentes y estado real (operativo, referencia, experimental, pendiente).
2. Validación reproducible de manchas de agua Sentinel-1.
3. Catálogo de grupos, fuentes y módulos compartidos.
4. Primer piloto nuevo: glaciares y nieve, reutilizando clima, DEM y teledetección.
5. Ampliaciones de geología, ciudades e infraestructura.
6. Dashboard de investigación, sin duplicar los dashboards operativos de DOTS.

## Criterios de aceptación

- Pruebas unitarias y de integración sin red mediante fixtures.
- Pruebas de contrato para el envelope.
- Registro de procedencia y unidades.
- Comparación con observaciones o productos de referencia independientes.
- Métricas de calidad y umbrales documentados por fenómeno.
- No publicar mapas o alertas como observaciones verificadas si solo son detecciones algorítmicas no validadas.

**Estado:** fundación documental y mapa de reutilización. No implica que todos los conectores estén activos ni que los grupos tengan ya interfaces implementadas.
