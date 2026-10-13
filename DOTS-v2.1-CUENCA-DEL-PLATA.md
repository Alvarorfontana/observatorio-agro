# DOTS Campo v2.1 — Cuenca del Plata: El Niño, alertas por lluvia en cabeceras y crecidas

## Qué suma
**Panel regional (`/panel`) → sección "Cuenca del Plata"** e **informe PDF** (`/api/fuentes/cuenca-informe`):
1. **Alerta temprana por lluvia en las cabeceras.** 21 subcuencas que aportan al Iguazú, Uruguay, Paraná, Paraguay, Bermejo y Pilcomayo (Brasil, Paraguay, Bolivia, Uruguay y el norte argentino). Lluvia de 15 días con el pronóstico por conjunto de ECMWF (51 corridas) y GFS (31). Niveles Atención, Alerta y Peligro con reglas declaradas; sube un escalón si el río de salida ya viene alto o si una represa aguas arriba suelta mucho. Ventana de llegada a cada localidad.
2. **El Niño semanal** (NOAA CPC, regiones 1+2, 3, 3.4 y 4) y **mapa de anomalía del mar** del Pacífico (GHRSST MUR vía NASA GIBS).
3. **Represas de Brasil (ONS, datos abiertos):** Salto Caxias (Iguazú), Itaipú y Porto Primavera (Paraná), Itá y Foz do Chapecó (Uruguay). Caudal medido.
4. **Ríos hoy y en 30 días** (GloFAS): Iguazú, Paraná, Paraguay y Uruguay en 10 localidades, contra lo normal para la fecha.
5. **Tiempos de traslado:** desfase estadístico entre estaciones (20 años) y llegada estimada del pico de cabecera.
6. **Peligro y acciones:** umbrales de crecida de 2, 5 y 20 años (Gumbel) y qué hacer en el campo en cada nivel.
7. **Imágenes de la zona:** VIIRS color real de la cuenca en alerta y lluvia satelital GPM IMERG (NASA GIBS).
8. **Fuentes oficiales por país** (INA, Prefectura, ANA, SGB, ONS, DMH, SENAMHI, INUMET, Salto Grande, CIC Plata).

**Tablero del lote:** humedad del suelo de NASA contra lo normal (segunda opinión) y entorno del lote con Overture Maps (caminos, construcciones, departamento). Ambos entran en el informe del lote.

## Configuración (una sola vez)
1. **Normales de la cuenca:** en `observatorio-agro` → Actions → "Normales de la Cuenca del Plata" → Run workflow. Tarda alrededor de una hora (respeta los límites gratuitos de Open-Meteo) y guarda `data/cuenca_normales.json`. Sin ese archivo el panel funciona igual, pero sin comparación con lo normal, sin umbrales de peligro y sin tiempos de traslado.
2. **Overture** corre dentro del procesamiento semanal de lotes (ver v2.0). No necesita configuración.

## Archivos
- `cuenca.py` — Niño semanal, lluvia por subcuenca, ríos, represas ONS, traslado, alerta temprana y mapas.
- `cuenca_report.py`, `report/cuenca.typ` — informe PDF de la cuenca.
- `scripts/normales_cuenca.py`, `.github/workflows/normales-cuenca.yml` — normales, desfases y crecidas de retorno.
- `soil_wetness.py` — humedad NASA POWER contra lo normal (`/api/fuentes/humedad-nasa`).
- `scripts/overture_lote.py` — entorno del lote (DuckDB sobre los GeoParquet públicos de Overture).
- `src/site/CuencaPanel.tsx` — sección del panel regional.

## Alcances
Orientativo. Los caudales GloFAS son simulados y se comparan con su propia serie. Las alturas oficiales de alerta y evacuación las fijan Prefectura e INA; ante una evacuación manda Defensa Civil.
