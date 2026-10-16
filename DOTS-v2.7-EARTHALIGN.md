# DOTS v2.7 · Descripción del estado atmosférico (EarthAlign / MeteoLIP)

## Qué es
[EarthAlign](https://mbzuai-oryx.github.io/EarthAlign/) (MBZUAI · ADIA Lab · UC San Diego) alinea datos del sistema
Tierra con lenguaje: **553.738 recortes de ERA5** (2000-2024, **63 variables**) con **cuatro estilos de descripción**
cada uno. **MeteoLIP** es el modelo meteo-texto (tipo CLIP/SigLIP, con su tokenizador MetTok) que, a partir de un
recorte de ERA5, recupera la descripción del estado del tiempo y clasifica fenómenos (ola de frío o de calor, tormenta,
etc.). El código parte de OpenCLIP.

En DOTS, esto agrega una **descripción en lenguaje natural del estado atmosférico** del punto, para leer de un vistazo
qué está pasando (o qué pasó) sin interpretar índices.

## Por qué no corre en la web
MeteoLIP es PyTorch y pesa cientos de MB; el recorte ERA5 es de 63 variables. La función de Vercel (250 MB, 60 s, sin
placa) no puede cargarlo ni calcularlo. Igual que el agua de Sentinel-2 (`geoai`) en la tarea semanal, EarthAlign corre
**aparte**, en una tarea de **GitHub Actions (CPU, gratis)**, y guarda su resultado en la rama `datos`
(`data/earthalign.json`). La web **sólo lee** ese archivo con `datastore.load` (caché 15 min, con copia local de
respaldo): una descripción nueva no obliga a publicar la web otra vez.

## Cómo entra en DOTS
**Fase 1 (hecha, verificable, sin torch).** `scripts/earthalign_build.py` baja los registros liberados del dataset
(`record_json`: `negsamp` = clima normal, `emdat` = catástrofe declarada), se queda con las muestras dentro de la
región de trabajo (sur de Sudamérica) y guarda por cada una: posición, fecha, categorías de evento y sus cuatro
descripciones. Nada de texto propio: son las descripciones ya alineadas del dataset. `earthalign.describe(lat,lon)`
devuelve la muestra más cercana (la fecha desempata) y `earthalign.status()` informa qué hay y qué falta.

Además, la tarea traduce cada descripción al **español** de forma **offline** con Argos Translate (sin clave ni límite
de uso; los modelos se descargan solos) y guarda `captions_es`. `describe()` devuelve el texto original y su versión
en español, más un `reading` en español listo para mostrar. Sólo traduce lo nuevo: recuerda las traducciones hechas
entre corridas, así que cada re-ejecución es incremental.

**Fase 2 (pendiente, necesita PyTorch).** Correr **MeteoLIP** sobre el recorte ERA5 de cada lote para describir
**cualquier** punto y fecha (no sólo los puntos del dataset): armar el tensor `(1, 63, H, W)` con el orden de variables
y la normalización de `era5_crop_stats.npz`, codificar meteo y texto y hacer recuperación/clasificación. Requiere
descargar los pesos (abajo), el reanálisis ERA5 del punto y una tarea específica. Queda listado en el `PENDING` de
`earthalign.py`.

## Rutas
- `GET /api/fuentes/earthalign?lat=..&lon=..[&fecha=aaaa-mm-dd]` → envelope DOTS con la descripción ya calculada del
  recorte más cercano; `sin dato` si todavía no se calculó o si no hay nada a menos de 150 km.
- `GET /api/fuentes/earthalign/estado` → diagnóstico: cuántas muestras hay y qué falta para activarlo.

## Puesta en marcha
1. Correr a mano la tarea **EarthAlign · descripciones del tiempo** (`.github/workflows/earthalign.yml`,
   `workflow_dispatch`). Baja `requirements.txt` (`requests`) e instala `argostranslate` (traducción en→es offline,
   modelos ~100 MB que se descargan solos); no necesita torch.
2. Verifica que quedó `data/earthalign.json` en la rama `datos` y que
   `/api/fuentes/earthalign/estado` responde `ready: true`.
3. Para la fase 2: descargar los pesos
   [MeteoLIP ViT-B/4 Full-MetTok](https://huggingface.co/datasets/MBZUAI/EarthAlign/tree/main/MeteoLIP/Meteo-CLIP/ViT-B-4_Full-MetTok),
   instalar el código de EarthAlign (`src/`), y sumar un paso ERA5 (Copernicus/ERA5) que arme el recorte de 63
   variables del lote.

## Licencias (revisar antes de un uso comercial)
EarthAlign **no declara una licencia propia** en su repositorio. El dataset mezcla fuentes con licencias distintas
(p. ej. EM-DAT **CC-BY-NC-ND**, NOAA dominio público, ERA5 **CC-BY**). El código parte de OpenCLIP. DOTS sólo guarda
**descripciones y metadatos** del dataset liberado y cita la fuente; no redistribuye ERA5 ni los pesos. Ver
`THIRD-PARTY-NOTICES.md`.

## Referencias
- Proyecto: https://mbzuai-oryx.github.io/EarthAlign/
- Código: https://github.com/mbzuai-oryx/EarthAlign · Artículo: https://arxiv.org/abs/2610.14624
- Dataset y pesos: https://huggingface.co/datasets/MBZUAI/EarthAlign
