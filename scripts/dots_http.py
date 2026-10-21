"""Cliente HTTP para que las tareas automáticas lean la API pública de DOTS.

- Si el proyecto de Vercel tiene "Deployment Protection" activa, la API redirige al login de Vercel y
  responde HTML. Antes eso pasaba como "200 OK" y los scripts fallaban más adelante (o podían mandar
  la página de login como newsletter). Ahora se corta con un mensaje claro.
- Si se carga el secreto VERCEL_AUTOMATION_BYPASS_SECRET (Vercel → Settings → Deployment Protection →
  Protection Bypass for Automation, gratuito), se envía en cada pedido y la protección deja pasar.
"""
import os
from urllib.parse import urlparse

import requests

SITE = os.environ.get('DOTS_SITE', 'https://observatorio-agro.vercel.app').rstrip('/')
BYPASS = os.environ.get('VERCEL_AUTOMATION_BYPASS_SECRET', '').strip()


class SitioProtegido(RuntimeError):
    pass


def session():
    s = requests.Session()
    s.headers['User-Agent'] = 'DOTS-tareas/1.0'
    if BYPASS:
        s.headers['x-vercel-protection-bypass'] = BYPASS
    return s


def protegido(r):
    """True si la respuesta es el login de Vercel y no la API de DOTS."""
    host = urlparse(r.url).hostname or ''
    if host != (urlparse(SITE).hostname or '') and host.endswith('vercel.com'):
        return True
    return r.status_code in (401, 403) and 'vercel' in (r.headers.get('server', '') + r.text[:2000]).lower()


def check(r, expect='json'):
    """Valida la respuesta: corta si es el login de Vercel o si no trae lo esperado."""
    if protegido(r):
        raise SitioProtegido(
            f'{SITE} está protegido por Vercel (Deployment Protection) y devolvió la página de login en lugar de datos. '
            'Desactivá la protección para producción o cargá el secreto VERCEL_AUTOMATION_BYPASS_SECRET en GitHub.')
    r.raise_for_status()
    kind = r.headers.get('Content-Type', '')
    if expect == 'json' and 'json' not in kind:
        raise ValueError(f'{r.url} respondió {kind or "sin tipo"} en lugar de JSON')
    if expect == 'pdf' and not r.content.startswith(b'%PDF-'):
        raise ValueError(f'{r.url} no devolvió un PDF')
    return r
