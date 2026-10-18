"""notify v1.0 — entrega de avisos por ntfy (push a teléfono o escritorio), estilo ntfy / Apprise.

Sin clave de API: se usa un canal (topic). Configurar NTFY_TOPIC y, opcionalmente, NTFY_URL para un
servidor propio (por defecto https://ntfy.sh). Si no hay topic, no se envía: se declara que falta la
credencial, igual que el resto de las fuentes protegidas de DOTS.
"""
import os

import research_connectors as c


def ntfy(title, message, priority=3, tags=None, click=None):
    """Publica un aviso en el canal ntfy configurado. Lanza ValueError si falta NTFY_TOPIC."""
    base = os.environ.get('NTFY_URL', 'https://ntfy.sh').rstrip('/')
    topic = os.environ.get('NTFY_TOPIC')
    if not topic:
        raise ValueError('requiere credencial: NTFY_TOPIC')
    headers = {'Title': str(title)[:120], 'Priority': str(priority)}
    if tags:
        headers['Tags'] = ','.join(str(t) for t in tags)
    if click:
        headers['Click'] = str(click)
    r = c.SESSION.post(f'{base}/{topic}', data=str(message)[:1200].encode('utf-8'), headers=headers, timeout=15)
    r.raise_for_status()
    return {'status': 'enviado', 'channel': 'ntfy', 'priority': int(priority)}
