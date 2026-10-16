"""earthalign v1.0 — descripción en lenguaje natural del estado atmosférico (EarthAlign / MeteoLIP).

EarthAlign (MBZUAI · ADIA Lab · UC San Diego) alinea datos del sistema Tierra con lenguaje: 553.738 recortes de ERA5
(2000-2024, 63 variables) con cuatro estilos de descripción cada uno. MeteoLIP es el modelo meteo-texto (tipo
CLIP/SigLIP) que, a partir de un recorte de ERA5, recupera la descripción del estado del tiempo y clasifica fenómenos
(ola de frío o de calor, tormenta, etc.).

Por qué no corre en la web: MeteoLIP es PyTorch y pesa cientos de MB; la función de Vercel (250 MB, 60 s, sin placa)
no puede cargarlo. Igual que el agua de Sentinel-2 (geoai) en la tarea semanal, EarthAlign corre APARTE en una tarea de
GitHub Actions (CPU) y guarda el resultado en la rama `datos` (data/earthalign.json). La web sólo lee ese archivo con
datastore.load: una descripción nueva no obliga a publicar la web otra vez.

describe(lat, lon[, fecha]) devuelve el envelope DOTS con la descripción ya calculada del recorte ERA5 más cercano al
punto (y a la fecha, si se indica). Mientras la tarea no se haya ejecutado responde 'sin dato' con el motivo: no se
inventan textos. Qué falta para activarlo: ver PENDING, DOTS-v2.7-EARTHALIGN.md y THIRD-PARTY-NOTICES.md.
"""
import math

import research_connectors as c
import datastore

DATASET = 'https://huggingface.co/datasets/MBZUAI/EarthAlign'
WEIGHTS = 'https://huggingface.co/datasets/MBZUAI/EarthAlign/tree/main/MeteoLIP'
CODE = 'https://github.com/mbzuai-oryx/EarthAlign'
PAPER = 'https://arxiv.org/abs/2610.14624'
STORE = 'earthalign.json'   # resultado precalculado en la rama datos (data/earthalign.json)
ORGANISM = 'MBZUAI · ADIA Lab · UC San Diego'
SCOPE = 'descripción del estado atmosférico (EarthAlign / MeteoLIP)'

# Los cuatro estilos con que el dataset describe cada condición (el mismo episodio, mirado distinto).
CAPTION_STYLES = ['natural_event_focused', 'impact_focused', 'physical_framing', 'atmospheric_pattern']
ERA5_VARIABLES = 63          # 25 de superficie + 3 de oleaje + 35 de niveles de presión (925/850/700/500/300 hPa)
MAX_KM = 150.0               # más lejos, la descripción de otro punto ya no representa al lote

# Qué falta para activar la descripción. Detalle y pasos en DOTS-v2.7-EARTHALIGN.md.
PENDING = [
    {'what': 'Tarea de cálculo en GitHub Actions (CPU, gratis)', 'where': '.github/workflows/earthalign.yml',
     'status': 'preparada; se activa a mano (workflow_dispatch) y luego por temporada'},
    {'what': 'Pesos MeteoLIP ViT-B/4 (formato OpenCLIP)', 'where': WEIGHTS,
     'status': 'se descargan en la tarea; no se versionan en el repositorio'},
    {'what': 'Recorte ERA5 de 63 variables del punto', 'where': 'Copernicus/ERA5',
     'status': 'lo arma la tarea (63 variables y normalización de era5_crop_stats.npz)'},
    {'what': 'Licencia', 'where': 'THIRD-PARTY-NOTICES.md',
     'status': 'EarthAlign no declara licencia propia; el dataset mezcla fuentes (EM-DAT CC-BY-NC-ND, NOAA dominio '
               'público). Revisar antes de un uso comercial.'},
]


def _km(lat1, lon1, lat2, lon2):
    """Distancia aproximada entre dos puntos, en kilómetros (haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _days(dt, other):
    """Diferencia absoluta en días entre dos fechas ISO (aaaa-mm-dd), o None si no se pueden leer."""
    from datetime import date

    def parse(v):
        try:
            return date.fromisoformat(str(v)[:10])
        except (TypeError, ValueError):
            return None
    a, b = parse(dt), parse(other)
    return abs((a - b).days) if a and b else None


def nearest(samples, lat, lon, dt=None):
    """Recorte ERA5 más cercano en el espacio (y la fecha desempata, si se indica). Devuelve (muestra, km)."""
    best, best_km, best_score = None, None, None
    for s in samples or []:
        try:
            slat, slon = float(s['lat']), float(s['lon'])
        except (KeyError, TypeError, ValueError):
            continue
        km = _km(lat, lon, slat, slon)
        if km > MAX_KM:
            continue
        pen = 0.0
        if dt:
            dd = _days(dt, s.get('time'))
            if dd is not None:
                pen = dd / 30.0 * 25.0     # cada 30 días de diferencia pesan como 25 km
        score = km + pen
        if best_score is None or score < best_score:
            best, best_km, best_score = s, km, score
    return best, (round(best_km, 1) if best is not None else None)


def _envelope(data=None, status='recibido', error=None):
    return c.envelope(data, CODE, SCOPE, ORGANISM, status=status, error=error)


def describe(lat, lon, dt=None):
    """Descripción del estado atmosférico ya calculada para el punto (y la fecha, si se da)."""
    lat, lon = float(lat), float(lon)
    doc = datastore.load(STORE)
    if not isinstance(doc, dict) or not doc.get('samples'):
        return _envelope(status='sin dato',
                         error='La descripción del estado atmosférico todavía no fue calculada. '
                               'Se genera en la tarea periódica (ver DOTS-v2.7-EARTHALIGN.md).')
    sample, km = nearest(doc['samples'], lat, lon, dt)
    if sample is None:
        return _envelope(status='sin dato',
                         error=f'Sin un recorte ERA5 relevado a menos de {int(MAX_KM)} km de este punto.')
    data = {'lat': sample.get('lat'), 'lon': sample.get('lon'), 'time': sample.get('time'),
            'distance_km': km, 'event': sample.get('event'), 'classification': sample.get('classification'),
            'captions': sample.get('captions') or {}, 'source_url': doc.get('source') or CODE}
    return _envelope(data)


def status():
    """Diagnóstico: cuántos recortes hay guardados y qué falta para activar la descripción."""
    doc = datastore.load(STORE)
    doc = doc if isinstance(doc, dict) else {}
    n = len(doc.get('samples') or [])
    return {'ready': n > 0, 'samples': n, 'generated_at': doc.get('generated_at'),
            'dataset': DATASET, 'weights': WEIGHTS, 'code': CODE, 'paper': PAPER, 'pending': PENDING}
