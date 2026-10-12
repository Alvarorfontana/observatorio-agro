# DOTS Campo v2.0 — Lotes guardados y procesamiento semanal con geoai

## Qué hace
1. **Lotes guardados en el navegador.** Sobreviven a recargar la página. Se pueden borrar desde "Variables del lote".
2. **Lotes en la nube (privado).** Con la clave del establecimiento, el botón "Guardar lotes en la nube" los manda al repositorio privado de datos. La web es pública; los contornos de los campos no.
3. **Procesamiento semanal gratuito.** Cada lunes a las 05:52 (hora argentina), GitHub Actions:
   - busca la imagen Sentinel-2 más reciente y despejada de cada lote (Earth Search, abierto);
   - detecta agua con **geoai** (`segment_water`, modelo preentrenado OmniWaterMask, sin placa gráfica);
   - calcula hectáreas de agua, cantidad de cuerpos de agua y NDVI medio dentro del lote;
   - guarda el resultado con su historial semanal en el repositorio privado.
4. **La web muestra los resultados**: recuadro "Agua detectada por satélite" en el Tablero, agua en azul sobre el lote en el Mapa y sección propia en el Informe PDF.

Sin la configuración de abajo, todo queda en pausa y la web sigue funcionando como antes.

## Configuración (una sola vez)
1. **Repositorio privado de datos.** En GitHub: New repository → nombre `dots-datos` → **Private** → marcar "Add a README" → Create.
2. **Token de acceso.** GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
   - Repository access: *Only select repositories* → `dots-datos`.
   - Permissions → Repository permissions → **Contents: Read and write**.
   - Copiar el token (empieza con `github_pat_`). No compartirlo por chat ni correo.
3. **Secreto para el procesamiento semanal.** En `observatorio-agro` → Settings → Secrets and variables → Actions → New repository secret:
   - Nombre `DOTS_DATA_TOKEN`, valor: el token.
4. **Variables en Vercel.** Proyecto `observatorio-agro` → Settings → Environment Variables (Production y Preview):
   - `DOTS_DATA_REPO` = `Alvarorfontana/dots-datos`
   - `DOTS_DATA_TOKEN` = el mismo token
   - `DOTS_WRITE_KEY` = una clave que elijas para el establecimiento (larga, sin espacios)
   - Después: Deployments → el último → Redeploy.
5. **Primera corrida.** En `observatorio-agro` → Actions → "Procesamiento semanal de lotes" → Run workflow. Tarda entre 10 y 30 minutos según la cantidad de lotes.

## Privacidad
- El código y los registros de GitHub Actions son públicos: el script no imprime nombres ni coordenadas.
- Lotes y resultados viven sólo en `dots-datos` (privado). Leerlos o escribirlos desde la web exige la clave del establecimiento.

## Límites
- Nubes: si en 45 días no hay imagen con menos de 30 % de nubes, el lote queda "sin dato" y se conserva el último resultado válido, marcado como anterior.
- Resolución 10 m: aguadas muy chicas (menos de 500 m² dentro del lote) no se cuentan.
- Es detección automática: conviene validar con recorrida o con la imagen del mapa.

## Archivos
- `scripts/procesar_lotes.py` — procesamiento (probado con escena sintética en `tests/test_procesar_lotes.py`).
- `.github/workflows/procesamiento-semanal.yml` — programación semanal.
- `lotes_store.py` — API `/api/lotes/*` (estado, sincronizar, resultado).
