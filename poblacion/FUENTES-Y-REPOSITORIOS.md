# Complementos para población, vulnerabilidad y respuesta

Selección de fuentes primarias revisadas el 14 de octubre de 2026. El núcleo implementado calcula exposición; los siguientes recursos son complementos identificados.

## Variables y cobertura

| Fuente | Información disponible/documentada | Uso propuesto | Criterio de integración |
|---|---|---|---|
| WorldPop total | Conteos de población en grilla | Total, densidad y exposición | Conservar producto, año, resolución y unidad; API o GeoTIFF. |
| WorldPop edad/sexo | Grupos de edad y sexo, productos 2015–2030, resoluciones según versión | Niñez y personas mayores expuestas, grupos por sexo | Elegir las capas exactas del país y producto, sin inferirlas del total. El lector local acepta cada capa como dataset independiente. |
| Populace | Distribución poblacional modelada, grilla anunciada de 40 m y actualización trimestral | Contexto poblacional temporal más detallado | Obtener producto y licencia correspondientes; lector GeoTIFF autorizado. No se confirmó una API pública reutilizable ni un desglose de salud/ingresos. |
| INDEC/REDATAM Censo 2022 | Tabulados censales y unidades geoestadísticas | Edad, viviendas y condiciones sociales según tabla publicada | Emparejar códigos de tabla y geografía del mismo operativo; verificar nivel de detalle y universo de cada variable. |
| Cartografía INDEC | Unidades censales, como fracciones | Cruce territorial con población censada | La precisión de la unidad censal limita lo que puede afirmarse dentro de una inundación más pequeña. |
| INFORM | Amenaza/exposición, vulnerabilidad y capacidad de respuesta | Contextualizar vulnerabilidad y capacidades a escala disponible | No trasladar un puntaje nacional o provincial a cada píxel como si fuera una medición local. La cobertura subnacional varía. |
| HDX | Catálogo de recursos humanitarios de distintos productores | Asentamientos, límites, infraestructura y otros datasets según país | Cada recurso tiene fecha, productor y licencia propios. No equivale a cobertura universal. |

### Variables que necesitan fuentes adicionales específicas

- Discapacidad, movilidad reducida y necesidades de apoyo: usar estadísticas o registros agregados autorizados adecuados al territorio. No inferirlas de imágenes o de la edad.
- Ingresos, pobreza y condiciones de vivienda: seleccionar un indicador y universo explícitos; un porcentaje de hogares no equivale a un porcentaje de personas.
- Agua y saneamiento: distinguir tipo de acceso, continuidad y calidad. Una tubería o edificio en un mapa no demuestra servicio efectivo.
- Centros de salud, escuelas y refugios: ubicación, capacidad, vigencia y accesibilidad deben verificarse con fuentes competentes. OSM/HDX pueden complementar, sin asumir exhaustividad.
- Accesibilidad y aislamiento: requieren red vial, transitabilidad y condiciones del evento; la distancia recta no representa tiempo de viaje.

## Otros cuatro repositorios verificados

| Repositorio | Aporte | Qué haría falta para integrarlo |
|---|---|---|
| [WFP-VAM/prism-app](https://github.com/WFP-VAM/prism-app) | Panel cartográfico para integrar amenazas y vulnerabilidad socioeconómica | Evaluar sus contratos de capas e indicadores y adaptar componentes a DOTS; no se copió el proyecto completo. |
| [OCHA-DAP/hdx-python-api](https://github.com/OCHA-DAP/hdx-python-api) | Acceso programático a HDX | Resolver datasets concretos por país/variable, revisar licencia, fecha y disponibilidad del recurso. |
| [CLIMADA-project/climada_python](https://github.com/CLIMADA-project/climada_python) | Evaluación de riesgo climático e impacto con funciones de vulnerabilidad | Entorno propio y funciones adecuadas al evento; revisar licencia GPL-3.0 y dependencias al incorporar. No convertir exposición en daños automáticamente. |
| [GFDRR/CCDR-tools](https://github.com/GFDRR/CCDR-tools) | Geoanálisis para evaluación de riesgos climáticos y desastres | Seleccionar rutinas y datasets aplicables al territorio, con su validación y condiciones. |

## Orden recomendado

1. Población total y amenaza concreta: núcleo de esta entrega.
2. Capas de edad y sexo para desgloses; registrar en el lector local.
3. Datos censales INDEC con códigos y cartografía compatibles.
4. Infraestructura y servicios con fuentes verificadas.
5. Evaluación de vulnerabilidad y capacidad de respuesta, con metodología pública.
6. Modelos de impacto y escenarios, cuando existan funciones calibradas y datos suficientes.

## Fuentes

- https://api.worldpop.org/v2/
- https://www.worldpop.org/datacatalog/
- https://hub.worldpop.org/project/categories?id=8
- https://www.worldpop.org/faq/
- https://data.worldpop.org/GIS/AgeSex_structures/Global_2015_2030/R2025A/2025/ARG/
- https://www.healthdata.org/data-tools-practices/interactive-data-visuals/populace
- https://www.planet.com/pulse/introducing-populace-mapping-humanity-in-unprecedented-detail/
- https://redatam.indec.gob.ar/
- https://geonode.indec.gob.ar/layers/geonode_data:geonode:fracciones_censales
- https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Subnational-risk

La página original de IHME respondió 403 al navegador de búsqueda; las condiciones y características de Populace se contrastaron con el anuncio de Planet, socio del producto. No se descargaron datos Populace ni se aceptaron condiciones en nombre del usuario.
