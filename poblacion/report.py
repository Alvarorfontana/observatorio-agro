"""Informe PDF de exposición poblacional (Typst), a partir del resultado que ya calculó la página.

Los números vienen del cliente: se validan tipos y rangos, las geometrías se vuelven a validar y se recalculan
superficies; no se agrega ningún dato que no esté en el resultado.
"""
import json
import math
import os
from datetime import datetime, timezone

from .geometry import polygon, area_km2, InputError

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'report')
TEMPLATE = os.path.join(BASE, 'poblacion.typ')
FONTS = os.path.join(BASE, 'fonts')
KIND = {'inundacion': 'Inundación', 'sequia': 'Sequía', 'incendio': 'Incendio', 'crecida': 'Crecida de río', 'calor': 'Calor extremo', 'otro': 'Otro evento'}
CAT = {'observado': 'Área observada', 'pronosticado': 'Área pronosticada', 'escenario_usuario': 'Escenario definido por el usuario'}
ENSO = {'el_nino': 'El Niño', 'la_nina': 'La Niña', 'neutral': 'Neutral', 'sin_especificar': 'Sin especificar'}
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _num(v, lo=0, hi=1e10):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        return None
    return float(v)


def fmt(v, d=0):
    if v is None:
        return 'Sin dato'
    s = f'{v:,.{d}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def _txt(v, n=200):
    return str(v or '')[:n]


def _rings(geom):
    m = geom.mapping()
    return m['coordinates'] if m['type'] == 'Polygon' else [r for poly in m['coordinates'] for r in poly]


def sketch(area, hazard, inter):
    """Coordenadas de las geometrías llevadas a un recuadro de 170 × 95 mm (norte arriba)."""
    pts = [p for r in _rings(area) for p in r] + ([p for r in _rings(hazard) for p in r] if hazard else [])
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = math.cos(math.radians((y0 + y1) / 2))
    w, h = max((x1 - x0) * k, 1e-9), max(y1 - y0, 1e-9)
    sc = min(160 / w, 85 / h)
    ox, oy = (170 - w * sc) / 2, (95 - h * sc) / 2

    def proj(g):
        return [[[round(ox + (x - x0) * k * sc, 2), round(95 - oy - (y - y0) * sc, 2)] for x, y in r] for r in _rings(g)] if g else []
    km = (x1 - x0) * 111.32 * k
    return {'area': proj(area), 'hazard': proj(hazard), 'inter': proj(inter), 'width_km': round(km, 1)}


def build(d, today=None):
    if not isinstance(d, dict):
        raise InputError('Falta el resultado del cálculo.')
    area = polygon(d.get('area'), 'zona de estudio')
    hazard = polygon(d['hazard'], 'área de amenaza') if isinstance(d.get('hazard'), dict) else None
    inter = polygon(d['intersection'], 'intersección') if isinstance(d.get('intersection'), dict) else None
    total = _num(d.get('population_total'))
    exposed = _num(d.get('population_exposed'))
    pct = _num(d.get('exposed_percent'), 0, 100)
    ev = d.get('event') if isinstance(d.get('event'), dict) else {}
    src = d.get('source') if isinstance(d.get('source'), dict) else {}
    a_km2 = area_km2(area)
    i_km2 = area_km2(inter) if inter else 0.0
    t = today or datetime.now(timezone.utc)
    year = d.get('year') if isinstance(d.get('year'), int) else None
    summary = []
    if total is not None:
        summary.append(f"En la zona de estudio ({fmt(a_km2, 1)} km²) residen unas {fmt(total)} personas según {_txt(src.get('provider'), 40) or 'WorldPop'} {year or ''}.")
    if exposed is not None:
        summary.append(f"Dentro del área de {KIND.get(ev.get('kind'), 'amenaza').lower()} ({fmt(i_km2, 2)} km² superpuestos) residen unas {fmt(exposed)} personas"
                       + (f", el {fmt(pct, 1)} % de la zona." if pct is not None else '.'))
    return {
        'title': 'DOTS · Población expuesta', 'generated': f'{t.day} de {MONTHS[t.month - 1]} de {t.year}',
        'total': fmt(total), 'exposed': fmt(exposed), 'pct': (fmt(pct, 1) + ' %') if pct is not None else 'Sin dato',
        'area_km2': fmt(a_km2, 1), 'inter_km2': fmt(i_km2, 2), 'density': fmt(total / a_km2 if total is not None and a_km2 else None, 1),
        'kind': KIND.get(ev.get('kind'), 'Amenaza'), 'category': CAT.get(ev.get('category'), _txt(ev.get('category'), 40)),
        'event_date': _txt(ev.get('date'), 10), 'event_source': _txt(ev.get('source'), 250), 'enso': ENSO.get(ev.get('enso'), 'Sin especificar'),
        'provider': _txt(src.get('provider'), 60) or 'WorldPop', 'year': str(year or ''), 'group': _txt(d.get('population_group'), 60) or 'Población total',
        'method': _txt(d.get('method'), 400), 'interpretation': _txt(d.get('interpretation'), 400),
        'notes': [_txt(n, 300) for n in (d.get('notes') or [])[:8] if isinstance(n, str)],
        'summary': summary, 'sketch': sketch(area, hazard, inter),
        'url': 'observatorio-agro.vercel.app/poblacion',
    }


def pdf(d, today=None):
    import typst
    data = json.dumps(build(d, today), ensure_ascii=False)
    out = typst.compile(TEMPLATE, root=BASE, font_paths=[FONTS], ignore_system_fonts=True, sys_inputs={'data': data})
    if out[:5] != b'%PDF-':
        raise RuntimeError('Typst no generó el PDF')
    return out
