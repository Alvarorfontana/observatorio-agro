# ATLAS LAB — Centro de investigación aplicada

ATLAS LAB organiza líneas de investigación científica y desarrollo tecnológico sobre la Tierra. No reemplaza DOTS Campo ni los observatorios existentes: reutiliza sus conectores, servicios y datos mediante contratos compartidos.

## Diferencia institucional y funcional: ATLAS LAB dentro de Observatorio DOT

**Observatorio DOT** es la plataforma de observación, consulta y comunicación: mantiene mapas, tableros, monitoreo, series, informes y productos dirigidos a usuarios. Sus unidades incluyen DOTS Campo, Observatorio Territorial, Observatorio Meteorológico e Hidrología y Riesgos.

**ATLAS LAB** es la unidad transversal de investigación aplicada y desarrollo tecnológico. Su trabajo es formular preguntas, evaluar fuentes, diseñar métodos, desarrollar algoritmos, medir incertidumbre, validar resultados y transferir capacidades aprobadas a los módulos de DOT.

| ATLAS LAB | Observatorio DOT |
|---|---|
| Investiga fenómenos y métodos | Monitorea variables y territorios |
| Diseña y prueba algoritmos | Ejecuta productos aceptados |
| Compara con referencias independientes | Presenta mapas, indicadores y series |
| Documenta errores e incertidumbre | Comunica estados, fechas y limitaciones |
| Desarrolla prototipos y pilotos | Opera funciones y servicios para usuarios |
| Transfiere métodos con criterios de aceptación | Mantiene los productos en seguimiento |

ATLAS LAB **no** es un décimo observatorio, no duplica los paneles de DOT, no reemplaza el backend ni crea una infraestructura paralela. Tampoco implica acreditación académica, afiliación o aval de los organismos citados.

### Líneas y profundidad de investigación

Los nueve grupos cubren: (G01) espectroscopia, reflectancia, firmas multibanda y teledetección; (G02) geodesia, DEM, LIDAR, altimetría e InSAR; (G03) hidrología continental, calidad de agua y oceanografía; (G04) climatología, extremos, ENSO, radiación y atmósfera; (G05) geomorfología, litología, alteración y recursos minerales; (G06) expansión urbana, isla de calor, infraestructura y exposición; (G07) IA, clasificación, anomalías, modelos físicos e incertidumbre; (G08) dinámica fluvial, cuencas, humedales, caudales, crecidas y anegamientos; (G09) glaciares, nieve, hielo, balance de masa, lagos glaciares y criósfera.

Cada grupo debe mantener ficha de misión, preguntas de investigación, métodos, fuentes, módulos reutilizados, productos esperados, limitaciones, responsable técnico y estado de madurez. El catálogo de fuentes es una cartera de investigación, no una afirmación de conexión activa.

### Fuentes prioritarias y reglas de incorporación

Argentina: CONAE, IANIGLA-CONICET, INA/SNIH, SMN, IGN y SEGEMAR. Internacionales: ESA/Copernicus, NASA Earthdata, USGS, NOAA, ECMWF, CHIRPS, JRC Global Surface Water, Microsoft Planetary Computer y NSIDC.

Para cada conjunto se registra productor, colección, identificador de producto, URL de acceso, licencia, atribución, resolución, cobertura, período, frecuencia, fecha de actualización, formato, restricciones, método de procesamiento y calidad. No se guardan credenciales en el catálogo ni en el frontend.

### Ciclo de transferencia

Un método pasa de ATLAS LAB a un módulo operativo solo cuando existe: (1) definición de variable y clase; (2) datos y licencia identificados; (3) procesamiento reproducible y versionado; (4) pruebas unitarias y de contrato; (5) comparación con referencia independiente; (6) métricas, incertidumbre y casos de fallo documentados; (7) criterios de monitoreo y reversión.

Estados obligatorios: `operativo_verificado`, `experimental`, `referencia_catalogada`, `pendiente` o `bloqueado`. Un pipeline que ejecuta no equivale a un método validado.

### Piloto Corrientes: alcance real

El detector existente procesa escenas Sentinel-1 RTC y genera geometrías candidatas de manchas de agua. La clase detectada es **agua nueva / cambio respecto de un fondo temporal**, no necesariamente toda el agua superficial. La evaluación debe comparar esa clase con una referencia que represente la misma definición, en la misma grilla, CRS y período. Una máscara de agua permanente o total no es una referencia equivalente.

El pipeline y el evaluador son componentes experimentales. La aprobación de CI prueba controles de software, no precisión geográfica. Hasta completar escenas reales revisadas y métricas por evento, no publicar el resultado como inundación confirmada ni como desempeño validado.

### Arquitectura compartida

Mantener Flask/Python como backend y Vite/React como frontend. ATLAS LAB reutiliza conectores, almacenamiento, cachés, cartografía, contratos y módulos de DOT. Los nuevos servicios deben integrarse al núcleo actual, con APIs y dependencias solo cuando una necesidad comprobada lo justifique. La interfaz de ATLAS LAB es una sección de investigación dentro del mismo producto, no una aplicación separada.

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
