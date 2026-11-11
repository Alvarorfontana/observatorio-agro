# DOTS v2.9 · Desmontes recientes por resta de NDVI

Panel Satelital → pestaña **Desmontes** → **Recientes · NDVI** (`/satelital#desmontes`).

## Qué hace

No se busca un campo. Se resta el verdor (NDVI de Sentinel-2) de toda la región entre dos ventanas de la misma época
del año y los desmontes más grandes aparecen solos. Es el método con el que se ubicó, sin coordenadas, la tala de un
centro de datos junto al río Oulujoki, en Finlandia.

- **Último verano**: diciembre–marzo contra el verano anterior. Se calcula cada 20 de abril.
- **Últimos 120 días**: contra los mismos días del año anterior. Se calcula el día 3 de cada mes.

Región por defecto: Salta, Jujuy, Tucumán, Santiago del Estero, Chaco, Formosa, Santa Fe, Corrientes, Misiones y
Entre Ríos. Se cambia al correr la tarea a mano.

## Cómo decide

| Paso | Regla |
|---|---|
| Candidato | NDVI antes ≥ 0,55, después ≤ 0,45 y caída ≥ 0,25 |
| Se descarta | agua o inundación en la segunda ventana (MNDWI), cultivos, ciudades y agua (ESA WorldCover), píxeles con menos de 2 pasadas sin nubes |
| Parche | píxeles vecinos unidos, desde 10 ha; los partidos por el borde de la grilla se vuelven a unir |
| Superficie | rango según el umbral: −0,25 (amplio), −0,35 y −0,45 (estricto) |

## Gravedad

Cada parche suma señales que se muestran en su globo:

| Señal | Puntos |
|---|---|
| Zona roja de la Ley de Bosques | 3 |
| Zona amarilla | 2 |
| Más de la mitad era bosque en 2020 (JRC, referencia del EUDR) | 2 (1 si es entre 20 y 50 %) |
| 500 ha o más | 2 (1 si es entre 100 y 500) |
| Pendiente media de 5° o más | 1 |
| A menos de 100 m de agua permanente | 1 |

Alta: 4 o más. Media: 2 o 3. Baja: menos de 2. Si el 30 % o más figura quemado (MODIS), el parche se marca como
**posible incendio** y no pasa de media.

## Segunda opinión AlphaEarth

Después de la resta de NDVI, la misma tarea mira cada parche en los mapas anuales de AlphaEarth Foundations
(Google DeepMind, colección `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, CC BY 4.0). Cada píxel de 10 m tiene un vector de
64 números por año que describe su cobertura. Se compara el año en que empieza la ventana «antes» con el último año
disponible hasta el fin de la ventana «después» (producto escalar promediado en el parche, a 30 m).

| Similitud | Lectura |
|---|---|
| 0,90 o más | sin cambio de cobertura: puede ser sequía, pastoreo o manejo |
| 0,70 a 0,90 | cambio moderado: raleo, desmonte parcial o pastura nueva |
| menos de 0,70 | cambio fuerte: confirma el desmonte o el cambio de uso |

No suma puntos de gravedad: los umbrales son orientativos y no están validados. Agrega una señal en el globo y el campo
`alphaearth` en cada parche. Si el último mapa anual todavía no cubre el período «después», no se evalúa. Si el paso
falla, los parches quedan como estaban (`continue-on-error`).

Archivos: `scripts/alphaearth_desmontes.py` y `tests/test_alphaearth_desmontes.py`.

## Ley de Bosques

No hay una capa nacional del OTBN que se pueda consultar. Para sumarla, subir a la rama `datos` un archivo
`data/otbn.geojson` con los polígonos provinciales y una propiedad `categoria` (I/II/III, o rojo/amarillo/verde).
Sin ese archivo la señal no se evalúa y la página lo aclara.

## Archivos

- `scripts/desmonte_ndvi.py` · cálculo en Earth Engine
- `.github/workflows/desmonte-ndvi.yml` · tarea mensual y de verano (secretos `GOOGLE_CLOUD_PROJECT` y `GOOGLE_APPLICATION_CREDENTIALS_JSON`)
- `tests/test_desmonte_ndvi.py` · 17 pruebas de la parte que no usa red
- Salida en la rama `datos`: `data/desmonte_ndvi_<ventana>.json` y fotos de antes y después de los 24 más grandes

## Límites

Es una señal para revisar, no una prueba de desmonte ilegal. Sequía extrema, pastura degradada o un incendio también
bajan el NDVI. La primera corrida no está validada en el terreno: conviene revisar a mano los diez primeros parches.
