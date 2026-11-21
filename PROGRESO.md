# Progreso · DOTS / Campo

Libreta del proyecto: qué hay, qué se hizo y qué falta. Se actualiza después de cada cambio, con la fecha.
Las reglas de trabajo están en `CLAUDE.md`. El detalle de cada versión está en los `DOTS-v*.md`.

## Qué hay hoy (resumen)

- Crecidas de la Cuenca del Plata: 34 localidades, avisos cada 2 horas (web, correo, Telegram, ntfy).
- Población expuesta por localidad (altura sobre el río, WorldPop) y barrios populares por radar (RENABAP).
- El Niño regional, clima de 30 años, heladas y rayos (GOES), focos de fuego, calor.
- Panel Satelital: aire, nieve, desmontes (NDVI + segunda opinión AlphaEarth + confirmación por radar), tormentas. Página `/sensores`.
- Panel EUDR / vender a Europa. Lente de Relieve (`/lente`).
- Gestor de Control: informe y avisos de fallas por correo.

## Registro

### 2026-11-16
- **Anegamientos en Corrientes con métodos de astronomía** (idea: cómo se separa una galaxia del fondo del cielo).
  Cada miércoles, en 8 zonas ribereñas (capital, Santa Lucía, Bella Vista, Goya, Esquina, Ituzaingó, Paso de los
  Libres, Mercedes): filtro Lee contra el speckle, «fondo» de cada píxel con recorte sigma sobre las pasadas del último
  año (sin los últimos 30 días), desvío z de la última pasada, umbral Otsu, apertura 3×3 y catálogo de manchas por
  regiones conectadas (superficie, centroide, intensidad). Hampel marca fechas raras en la serie de % de agua.
  Rangos: z medio ≤ −5 fuerte · −5 a −4 moderada · −4 a −3 leve; mínimo 1 ha. Sentinel-1 RTC de Planetary Computer,
  gratis y sin secretos. `scripts/manchas_agua.py` (núcleo), `scripts/anegamientos.py`, `anegamientos.yml`.
  Salida liviana en la rama datos: `data/anegamientos.json` y `.geojson`. Orientativo.
  Primera corrida real: el recuadro de Corrientes capital y Paso de los Libres caía en el borde entre dos tramos de
  la misma pasada y daba cero agua. Corregido: se unen todos los tramos del día, la zona no se informa si la pasada
  cubre menos del 60 % del recuadro, cada píxel necesita 5 pasadas de fondo y Otsu solo vale entre −24 y −15 dB
  (más arriba confunde suelo mojado con agua; si no, −18 dB fijo). Cada zona elige la órbita cuya huella cubre
  el recuadro: algunas franjas lo rozan sin cubrirlo.
  Página **`/anegamientos`** (menú «Más módulos» y menú del celular): mapa satelital con recuadros y manchas, tabla
  por zona con el último estado del INA y si coincide (regla en `anegamientos_api.py`, ruta
  `/api/fuentes/anegamientos`), barras de agua habitual/hoy/nueva, serie con fechas raras, rangos y límites.
  Validación 16/11: coinciden 6 zonas con escala del INA; Paso de los Libres no (menos de la mitad del agua habitual
  con el Uruguay en atención: posible viento sobre el río), queda marcada «en revisión».
  Pendiente: revisar Paso de los Libres (probar polarización VH o descartar pasadas con viento); validar contra GFM.

### 2026-11-14
- **Alerta temprana de estrés hídrico por lote** (idea tomada de quantag, código propio). En el procesamiento semanal,
  cada lote compara su NDVI y su LSWI (agua en la hoja) con la misma época (±15 días) de hasta 5 años anteriores.
  Rangos: desvío menor a −1,5 fuerte · −1,5 a −0,75 moderado · mayor a −0,75 normal. Si baja el LSWI antes que el
  NDVI lo marca como señal temprana. La base se calcula una vez por semana del año y queda guardada en el lote.
  `scripts/anomalia_lote.py`, tarjeta nueva en el tablero del lote. Orientativo. `DOTS_ANOMALIA=0` lo apaga.
  Pendiente: validar con lotes que hayan tenido sequía conocida (campaña 2022/23).

### 2026-11-12
- Desmontes: **confirmación por radar Sentinel-1** (banda VH) en cada parche. Separa monte cortado de monte seco:
  −2 dB o menos confirma · −2 a −1 leve · más de −1 sin cambio. Bloque con rangos y barras en el panel, señal en el
  globo, mínimo de 3 pasadas por ventana. `scripts/radar_desmontes.py`, paso nuevo en `desmonte-ndvi.yml`. No toca
  la gravedad: los umbrales son orientativos. Pendiente: validar con los diez primeros parches.
- **Meteograma 7 días** (Clima avanzado → primera pestaña): toda la semana de la localidad en una lámina, idea tomada
  de los meteogramas de weathermodels.com. Cuatro paneles horarios con el eje de tiempo compartido: temperatura y punto
  de rocío (línea de 0 °C), lluvia y probabilidad, viento y ráfagas (umbral de 15 km/h para pulverizar), nubosidad y
  humedad. Tabla diaria con avisos (helada, rocío, ráfagas, lluvia intensa) y rangos de lectura. Open-Meteo, sin clave.
  `src/site/Meteograma.tsx`.

### 2026-11-11
- Desmontes: **segunda opinión AlphaEarth** (mapas anuales de Google DeepMind) en cada parche, con umbrales
  (menos de 0,70 cambio fuerte · 0,70 a 0,90 moderado · 0,90 o más sin cambio), bloque destacado y barras.
  `scripts/alphaearth_desmontes.py`. No toca la gravedad: los umbrales son orientativos.
- **Conteo de ganado gratis**: RF-DETR Nano (Apache 2.0) + mosaico SAHI en GitHub Actions, sin RunPod.
  Tarea "Conteo de ganado" a pedido; gráfico por cuadro con piso, techo y mediana. `DOTS-v3.0-CONTEO-GANADO.md`.
- Página **`/sensores`**: cuántos píxeles ocupa un objeto en cada fuente y qué ve cada una.
- Se crearon `CLAUDE.md` y este archivo.

## Pendiente

- [ ] Primera corrida real de AlphaEarth (tarea mensual del día 3 o a mano con ventana «verano»).
- [ ] Primera prueba del conteo de ganado con una foto de drone de un rodeo.
- [ ] **Validación**: armar 20–30 casos revisados a mano (desmontes confirmados, fotos de rodeos contadas) para medir
      cuánto acierta cada módulo y sacar la palabra «orientativo».
- [ ] Afinar RF-DETR con fotos de rodeos argentinos (gratis en Colab).
- [ ] «Avisame» por localidad: suscripción por correo a una sola localidad, no a las 34.
- [ ] Idea: superficie de agua en embalses y lagunas (Sentinel-2 + Sentinel-1) contra el promedio histórico.

## 2026-11-20 · Población expuesta en todas las localidades ribereñas
- Nuevo `scripts/poblacion_expuesta.py` y workflow `poblacion-expuesta.yml` (a pedido y los lunes): corre el cálculo de población cerca del río (MERIT Hydro HAND + WorldPop 2020, 15 km) para cada estación de la Cuenca del Plata y guarda `data/poblacion_expuesta.json` en la rama datos.
- Antes solo se calculaba para la localidad del digest (Corrientes).
- Pendiente: mostrarlo en la web y en el digest de El Niño y crecidas.
## 2026-11-20 · Arreglos de gestores y del digest de El Niño y crecidas
- Digest: la fase de El Niño salía «sin dato» (se leía un campo que no existe); ahora muestra fase e intensidad.
- Digest: el tema crecidas se filtraba a la estación más cercana a Corrientes (1 puerto); con `cuenca=1` trae todas.
- Avisos: cada corrida guarda `data/avisos_pulso.json` con la hora de revisión; el Control mira ese archivo (antes daba
  «viejo» cuando simplemente no había cambios de nivel).
- Telegram desactivado en `gestores/fichas.yml`: los avisos van por correo (Resend).
- El Niño por satélite: la humedad del suelo (SMAP) nunca se calculaba por un error del reductor con dos bandas.
- Atmósfera ENSO: si el OLR o la presión de NOAA PSL dejan de actualizarse, se completan con los índices del CPC.
- Pendiente: tabla de IRI Columbia (la página arma la tabla en el navegador), 132 celdas de desmontes sin calcular,
  clorofila MODIS frenada en 2025-11, y que GitHub demora las tareas programadas (disparo externo con cron-job.org).
- Columbia (CCSR/IRI) dejó de publicar la tabla de probabilidades: ahora se guarda el párrafo original con los porcentajes.
- Desmontes: las 132 celdas fallaron porque Earth Engine pasó la cuenta a «modo restringido» (se superó la cuota
  no comercial) y rechazó pedidos simultáneos. Se bajó de 6 a 3 pedidos a la vez y se agregó una segunda vuelta,
  de a una celda con pausas, para las que fallen.

## 2026-11-20 · Gestor de evacuados
- Nuevo `scripts/evacuados.py` y workflow `evacuados.yml` (todos los días y a pedido): lee el «Monitoreo de Amenazas
  Naturales» diario de la OPS, que resume los partes oficiales (Agencia Federal de Emergencias, Defensas Civiles, SEN
  de Paraguay, SINAE de Uruguay, Defesa Civil de Brasil), y guarda en `data/evacuados.json` los párrafos de Argentina,
  Paraguay, Uruguay y Brasil con cifras, organismo y enlace. DOTS no estima: un día sin parte queda sin dato.
- El informe diario del Control suma la sección «Evacuados · partes oficiales».
- Pendiente: página /evacuados con mapa y la lista de organismos que no publican; sumar fuentes provinciales directas.
