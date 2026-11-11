# Progreso · DOTS / Campo

Libreta del proyecto: qué hay, qué se hizo y qué falta. Se actualiza después de cada cambio, con la fecha.
Las reglas de trabajo están en `CLAUDE.md`. El detalle de cada versión está en los `DOTS-v*.md`.

## Qué hay hoy (resumen)

- Crecidas de la Cuenca del Plata: 34 localidades, avisos cada 2 horas (web, correo, Telegram, ntfy).
- Población expuesta por localidad (altura sobre el río, WorldPop) y barrios populares por radar (RENABAP).
- El Niño regional, clima de 30 años, heladas y rayos (GOES), focos de fuego, calor.
- Panel Satelital: aire, nieve, desmontes (NDVI + segunda opinión AlphaEarth), tormentas. Página `/sensores`.
- Panel EUDR / vender a Europa. Lente de Relieve (`/lente`).
- Gestor de Control: informe y avisos de fallas por correo.

## Registro

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
