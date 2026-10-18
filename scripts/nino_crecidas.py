"""El Niño y crecidas: digest cada 2 h (corre en GitHub Actions).

1. Lee la API pública de DOTS: niveles de la cuenca (INA · escalas de Prefectura), estado del Pacífico (NOAA)
   y el newsletter HTML del motor de temas (con la procedencia de cada bloque).
2. Guarda data/nino_crecidas.json (estado compacto, para la web) y data/nino_newsletter.html.
3. Una vez por día guarda además el PDF snapshot data/nino_crecidas.pdf.

El envío por correo lo hace scripts/nino_newsletter.py. Sin credenciales no rompe: sólo deja los archivos.

Uso: python scripts/nino_crecidas.py
"""
import json
import os
import sys
from datetime import datetime, timezone

import requests

SITE = os.environ.get('DOTS_SITE', 'https://observatorio-agro.vercel.app')
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
STATE = os.path.join(DATA, 'nino_crecidas.json')
HTML = os.path.join(DATA, 'nino_newsletter.html')
PDF = os.path.join(DATA, 'nino_crecidas.pdf')
TEMAS = ['nino', 'crecidas', 'inundaciones', 'evacuados', 'poblaciones']
# Punto de referencia del digest: Corrientes, centro de la cuenca media del Plata.
LAT, LON = -27.47, -58.83
ORDER = {'Normal': 0, 'Atención': 1, 'Alerta': 2, 'Evacuación': 3}
HOUR = 8


def load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def get_json(path, timeout=90):
    r = requests.get(f'{SITE}/api/fuentes/{path}', timeout=timeout)
    r.raise_for_status()
    return r.json()


def unwrap(j):
    """La API envuelve el dato como {status, data}; algunos endpoints devuelven el dato pelado."""
    return j.get('data') if isinstance(j, dict) and 'data' in j else j


def stations():
    """Localidades de la cuenca con su nivel (Normal, Atención, Alerta, Evacuación)."""
    j = get_json('alertas-resumen')
    d = j.get('data') if isinstance(j, dict) else None
    return (d or {}).get('stations') or (j.get('stations') if isinstance(j, dict) else None) or []


def enso():
    """Estado del Pacífico según NOAA (fase y anomalía ONI), mejor esfuerzo."""
    try:
        d = unwrap(get_json('el-nino')) or {}
        ph = d.get('phase')
        estado = (ph or {}).get('es') or (ph or {}).get('en') if isinstance(ph, dict) else None
        oni = d.get('oni')
        return {'estado': estado, 'oni': oni.get('anom') if isinstance(oni, dict) else None}
    except Exception:
        return {'estado': None, 'oni': None}


def newsletter(nombre):
    r = requests.get(f'{SITE}/api/fuentes/newsletter-temas',
                     params={'temas': ','.join(TEMAS), 'nombre': nombre, 'lat': LAT, 'lon': LON}, timeout=180)
    r.raise_for_status()
    return r.text


def pdf_snapshot():
    r = requests.post(f'{SITE}/api/fuentes/informe-temas',
                      json={'temas': TEMAS, 'nombre': 'El Niño y crecidas', 'lat': LAT, 'lon': LON}, timeout=180)
    return r.content if r.ok and r.content[:5] == b'%PDF-' else None


def counts(st):
    c = {'Normal': 0, 'Atención': 0, 'Alerta': 0, 'Evacuación': 0}
    for s in st:
        if s.get('level') in c:
            c[s['level']] += 1
    return c


def worst(st):
    ranked = [s for s in st if s.get('level') in ORDER]
    if not ranked:
        return None
    s = max(ranked, key=lambda x: ORDER[x['level']])
    return {'id': s.get('id'), 'place': s.get('place'), 'river': s.get('river'),
            'level': s.get('level'), 'height': s.get('height')}


def main():
    now = datetime.now(timezone.utc)
    prev = load(STATE, {})
    try:
        st = stations()
    except Exception as e:
        print(f'Sin datos de la cuenca: {e}')
        return 1
    if not st:
        print('Sin localidades en alertas-resumen: no se cambia nada.')
        return 0
    alto = [{'id': s.get('id'), 'place': s.get('place'), 'river': s.get('river'), 'level': s.get('level')}
            for s in st if s.get('level') in ('Alerta', 'Evacuación')]
    e = enso()
    subject = f'DOTS · El Niño y crecidas · {now:%d/%m/%Y %H:%M} UTC'
    digest = {'updated': now.isoformat(timespec='minutes'), 'version': 1, 'fuente': SITE,
              'niveles': counts(st), 'peor': worst(st), 'alertas': alto, 'enso': e,
              'enviado_el': prev.get('enviado_el'), 'pdf_el': prev.get('pdf_el')}
    save(STATE, digest)
    print(f"Estado: {digest['niveles']}. Peor: {(digest['peor'] or {}).get('place')}. "
          f"Alertas: {len(alto)}. El Niño: {e.get('estado')}.")
    try:
        html = newsletter(subject)
        if len(html) > 500:
            with open(HTML, 'w', encoding='utf-8') as f:
                f.write(html)
            digest['newsletter'] = {'subject': subject, 'bytes': len(html)}
            save(STATE, digest)
            print(f'Newsletter HTML guardado ({len(html)} bytes).')
        else:
            print('Newsletter vacío: no se guarda.')
    except Exception as ex:
        print(f'No se pudo armar el newsletter: {ex}')
    if now.hour >= HOUR and (prev.get('pdf_el') or '')[:10] != now.date().isoformat():
        try:
            b = pdf_snapshot()
            if b:
                with open(PDF, 'wb') as f:
                    f.write(b)
                digest['pdf_el'] = now.isoformat(timespec='minutes')
                save(STATE, digest)
                print(f'PDF snapshot guardado ({len(b)} bytes).')
            else:
                print('El informe no devolvió un PDF válido.')
        except Exception as ex:
            print(f'No se pudo armar el PDF: {ex}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
