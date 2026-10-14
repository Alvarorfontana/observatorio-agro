"""avisos_web — feed público de avisos de crecidas (JSON y RSS) y suscripción por correo.

El feed lo escribe la tarea programada (scripts/avisos.py) en data/avisos.json. La suscripción guarda el correo en una
lista (audiencia) de Resend, que permite dar de baja con un enlace en cada correo. Variables en Vercel:
  RESEND_API_KEY, RESEND_AUDIENCE_ID   suscripción por correo
  TELEGRAM_CHANNEL_URL                  enlace público al canal de Telegram (p. ej. https://t.me/dots_alertas)
Sin esas variables, la web lo informa y no simula suscripciones.
"""
import json
import os
import re
from xml.sax.saxutils import escape

import research_connectors as c

FEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'avisos.json')
SITE = 'https://observatorio-agro.vercel.app'
EMAIL = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$')


def channels():
    tg = os.environ.get('TELEGRAM_CHANNEL_URL', '')
    return {'email': bool(os.environ.get('RESEND_API_KEY') and os.environ.get('RESEND_AUDIENCE_ID')),
            'telegram_url': tg if tg.startswith('https://t.me/') else None,
            'feed_json': f'{SITE}/api/fuentes/avisos', 'feed_rss': f'{SITE}/api/fuentes/avisos?formato=rss',
            'widget': f'{SITE}/avisos-widget/'}


def feed(localidad=None, limit=50):
    try:
        with open(FEED, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {'items': []}
    items = data.get('items') or []
    if localidad:
        items = [i for i in items if i.get('id') == localidad]
    return {'updated': data.get('updated'), 'items': items[:limit], 'channels': channels()}


def rss(data):
    items = ''.join(
        f"<item><title>{escape(i['place'])}: {escape(i['to'])}</title><link>{SITE}/alertas</link>"
        f"<guid isPermaLink=\"false\">{escape(i['id'])}-{escape(i.get('at', ''))}</guid>"
        f"<pubDate>{escape(i.get('at', ''))}</pubDate><description>{escape(i.get('text', ''))}</description></item>"
        for i in data['items'])
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f'<title>DOTS · Avisos de crecidas</title><link>{SITE}/alertas</link>'
            '<description>Cambios de nivel (Normal, Atención, Alerta, Evacuación) en 34 localidades de la Cuenca del Plata. Datos: INA y Prefectura.</description>'
            '<language>es-ar</language>' + items + '</channel></rss>')


def subscribe(d):
    if (d.get('website') or '').strip():          # campo trampa para robots
        raise ValueError('Suscripción rechazada')
    email = str(d.get('email') or '').strip().lower()
    if not EMAIL.match(email):
        raise ValueError('Escribí un correo válido')
    key, aud = os.environ.get('RESEND_API_KEY'), os.environ.get('RESEND_AUDIENCE_ID')
    if not (key and aud):
        return {'status': 'sin configurar', 'error': 'La suscripción por correo todavía no está activada. Mientras tanto podés seguir el canal de Telegram o el feed RSS.'}
    r = c.SESSION.post(f'https://api.resend.com/audiences/{aud}/contacts', timeout=20,
                       headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                       json={'email': email, 'unsubscribed': False})
    if r.status_code >= 400:
        return {'status': 'error', 'error': 'No se pudo registrar el correo. Probá de nuevo más tarde.'}
    return {'status': 'suscripto', 'message': 'Listo: vas a recibir un correo cada vez que una localidad cambie de nivel.'}
