"""Newsletter de El Niño y crecidas por correo (Resend), una vez por día.

Lee el estado y el HTML que dejó scripts/nino_crecidas.py. No envía si ya se envió hoy (UTC) ni antes de las
HOUR UTC. Con NINO_FORZAR=1 se puede forzar. Sin RESEND_API_KEY / RESEND_AUDIENCE_ID no rompe: lo informa.
El texto es formal, sin emojis: es información pública. Ante una emergencia manda Defensa Civil.

Uso: python scripts/nino_newsletter.py
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
HOUR = 8
FOOTER = ('<hr style="border:0;border-top:1px solid #e4e7ec;margin:18px 0">'
          '<p style="color:#667085;font-size:12px">DOTS · Observatorio. Datos: INA y escalas de Prefectura, '
          'NOAA CPC, Copernicus y JRC. Ante una emergencia manda Defensa Civil. '
          'Para dejar de recibir el newsletter usá el enlace de baja: {{{RESEND_UNSUBSCRIBE_URL}}}</p>')


def load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def decision(state, now, force):
    """→ (enviar, motivo). Una vez por día en UTC y sólo desde HOUR."""
    if force:
        return True, 'forzado'
    if (state.get('enviado_el') or '')[:10] == now.date().isoformat():
        return False, 'ya se envió hoy'
    if now.hour < HOUR:
        return False, f'fuera de la hora de envío (UTC ≥ {HOUR})'
    return True, 'ventana diaria'


def send(subject, html):
    key, aud = os.environ.get('RESEND_API_KEY'), os.environ.get('RESEND_AUDIENCE_ID')
    if not (key and aud):
        return 'sin configurar'
    sender = os.environ.get('AVISOS_FROM') or os.environ.get('CONTACT_FROM') or 'DOTS Campo <onboarding@resend.dev>'
    body = html.replace('</body>', FOOTER + '</body>') if '</body>' in html else html + FOOTER
    h = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    r = requests.post('https://api.resend.com/broadcasts', headers=h, timeout=30, json={
        'audience_id': aud, 'from': sender, 'subject': subject, 'html': body,
        'name': f'El Niño y crecidas {datetime.now(timezone.utc):%Y-%m-%d}'})
    if not r.ok:
        return f'error {r.status_code}'
    bid = r.json().get('id')
    r2 = requests.post(f'https://api.resend.com/broadcasts/{bid}/send', headers=h, timeout=30, json={})
    return 'enviado' if r2.ok else f'error {r2.status_code}'


def main():
    now = datetime.now(timezone.utc)
    state = load(STATE, {})
    if not state:
        print('No hay estado (corré primero scripts/nino_crecidas.py).')
        return 0
    if not os.path.exists(HTML):
        print('No hay newsletter HTML guardado: no se envía.')
        return 0
    ok, why = decision(state, now, os.environ.get('NINO_FORZAR') == '1')
    if not ok:
        print(f'No se envía: {why}.')
        return 0
    html = open(HTML, encoding='utf-8').read()
    subject = (state.get('newsletter') or {}).get('subject') or f'DOTS · El Niño y crecidas · {now:%d/%m/%Y}'
    res = send(subject, html)
    print(f'Correo: {res} ({why}). Detalle: {SITE}/nino-crecidas')
    if res == 'enviado':
        state['enviado_el'] = now.isoformat(timespec='minutes')
        save(STATE, state)
    return 0


if __name__ == '__main__':
    sys.exit(main())
