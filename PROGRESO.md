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

### 2026-11-12
- **Gestor de evacuados** (`gestor-evacuados.yml`, lunes 08:41): busca cada semana partes de evacuados,
  autoevacuados, desplazados, desabrigados y desalojados en 95 lugares de Argentina, Uruguay, Paraguay y Brasil
  (municipios, provincias o estados y organismos nacionales), en Google Noticias (RSS público, sin clave). Saca las
  cifras del titular, las deja «a verificar» con su enlace y marca los lugares sin novedades. Guarda en la rama
  datos (`data/evacuados_partes.json` y un histórico) y manda el informe por correo (Resend) y al issue «Partes de
  evacuados». Lugares en `gestores/evacuados.yml`. Lo vigila el Gestor de Control. Motivo: ningún país publica una
  base automática de evacuados; sólo hay partes sueltos de SINAGIR, Defensa Civil, SINAE/Cecoed, SEN y Defesa Civil.
  También busca por dominio en los sitios de 16 organismos oficiales (SINAGIR, gobiernos provinciales, SINAE, SEN,
  Defesa Civil) y en GDELT como segunda red; avisa qué organismos no publicaron partes con cifras.
- **Página `/evacuados`**: mapa de evacuados de la Cuenca del Plata (último parte por zona, tamaño por personas,
  cuadrados para los lugares que solo informan familias, gris para temporales), evolución de personas y de familias,
  tabla «Quién publica datos y quién no» (14 jurisdicciones: 5 sin parte encontrado), registro de 31 partes
  verificados con fuente y CSV, lo que detectó el gestor esta semana «a verificar», rangos de lectura y límites.
  Datos verificados en `public/evacuados/base.json`; lo del gestor se lee de la rama datos. Enlaces desde la portada
  («Ahora en la región») y desde El Niño y crecidas.
  Pendiente: correr el gestor la primera vez a mano y ajustar las palabras si trae ruido; pasar a mano al registro
  los partes que se confirmen; cargar `CONTROL_EMAIL` y `RESEND_API_KEY` para que llegue el correo.
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
