"""Avisos automáticos de crecidas (corre en GitHub Actions cada 2 horas, gratis).

1. Lee las alturas y niveles oficiales de la web de DOTS (INA · escalas de Prefectura).
2. Compara el nivel de cada localidad (Normal, Atención, Alerta, Evacuación) con el último guardado en
   data/avisos_estado.json.
3. Si cambió, agrega el aviso a data/avisos.json (feed público para la web, RSS y otras páginas) y lo manda:
   - al canal de Telegram de DOTS, si están TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID (secretos del repositorio);
   - por correo a la lista de suscriptores de Resend, si están RESEND_API_KEY y RESEND_AUDIENCE_ID.
Texto formal, sin emojis: es información pública de emergencia. Ante una evacuación manda Defensa Civil.

Uso: python scripts/avisos.py
"""
import json
import os
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # dots_http vive al lado
from dots_http import SITE, check, session
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, '..', 'data', 'avisos_estado.json')
FEED = os.path.join(HERE, '..', 'data', 'avisos.json')
ORDER = {'Normal': 0, 'Atención': 1, 'Alerta': 2, 'Evacuación': 3}
MAX_FEED = 200


def load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def num(v, d=2):
    return '—' if v is None else f'{v:.{d}f}'.replace('.', ',')


def changes(prev, stations):
    """→ lista de avisos por cambio de nivel. La primera vez sólo guarda el estado (no avisa todo junto)."""
    out = []
    for s in stations:
        lvl = s.get('level')
        if lvl not in ORDER:
            continue
        old = (prev.get(s['id']) or {}).get('level')
        if old is None or old == lvl:
            continue
        up = ORDER[lvl] > ORDER.get(old, 0)
        out.append({'id': s['id'], 'place': s['place'], 'river': s['river'], 'from': old, 'to': lvl, 'up': up,
                    'height': s.get('height'), 'alert': s.get('alert'), 'evac': s.get('evac'), 'date': s.get('date'),
                    'trend_m_day': s.get('trend_m_day')})
    return out


def text(a):
    verb = 'sube' if a['up'] else 'baja'
    t = (f"{a['place']} (río {a['river']}): el nivel {verb} de {a['from']} a {a['to']}. "
         f"Altura {num(a['height'])} m el {a['date'] or ''}; alerta {num(a['alert'])} m, evacuación {num(a['evac'])} m.")
    if a.get('trend_m_day') is not None:
        t += f" Tendencia {'+' if a['trend_m_day'] > 0 else ''}{num(a['trend_m_day'])} m por día."
    if a['to'] == 'Evacuación':
        t += ' Seguir las indicaciones de Defensa Civil.'
    return t


NTFY_TOPIC = os.environ.get('NTFY_TOPIC', 'dots-crecidas-cuenca-plata')


def ntfy(msgs, worst):
    """Notificación al celular por ntfy.sh (gratis, sin cuenta): quien instala la app ntfy y se suscribe al tema la recibe."""
    if os.environ.get('NTFY_DISABLED') == '1':
        return 'desactivado'
    body = '\n\n'.join(msgs) + f'\n\nDetalle y fuentes: {SITE}/alertas'
    r = requests.post(f'https://ntfy.sh/{NTFY_TOPIC}', data=body.encode('utf-8'), timeout=30, headers={
        'Title': f'DOTS · Crecidas: {worst}'.encode('utf-8'), 'Priority': 'high' if 'Evacuación' in worst or 'Alerta' in worst else 'default',
        'Click': f'{SITE}/alertas', 'Tags': 'ocean'})
    return 'enviado' if r.ok else f'error {r.status_code}'


def telegram(msgs):
    tok, chat = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not (tok and chat):
        return 'sin configurar'
    body = 'DOTS · Avisos de crecidas\n\n' + '\n\n'.join(msgs) + f'\n\nDetalle y fuentes: {SITE}/alertas'
    r = requests.post(f'https://api.telegram.org/bot{tok}/sendMessage', json={'chat_id': chat, 'text': body[:4000], 'disable_web_page_preview': True}, timeout=30)
    return 'enviado' if r.ok else f'error {r.status_code}'


def email(msgs, worst):
    key, aud = os.environ.get('RESEND_API_KEY'), os.environ.get('RESEND_AUDIENCE_ID')
    if not (key and aud):
        return 'sin configurar'
    sender = os.environ.get('AVISOS_FROM') or os.environ.get('CONTACT_FROM') or 'DOTS Campo <onboarding@resend.dev>'
    html = ('<div style="font-family:Arial,sans-serif;font-size:15px;color:#101828">'
            '<p><b>DOTS · Avisos de crecidas</b></p>' + ''.join(f'<p>{m}</p>' for m in msgs) +
            f'<p>Detalle, fuentes y pronóstico: <a href="{SITE}/alertas">{SITE}/alertas</a></p>'
            '<p style="color:#667085;font-size:12px">Datos: INA y escalas de Prefectura. Ante una evacuación manda Defensa Civil. '
            'Para dejar de recibir estos avisos usá el enlace de baja: {{{RESEND_UNSUBSCRIBE_URL}}}</p></div>')
    h = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    r = requests.post('https://api.resend.com/broadcasts', headers=h, timeout=30, json={
        'audience_id': aud, 'from': sender, 'subject': f'DOTS · Crecidas: {worst}', 'html': html, 'name': f'Avisos {datetime.now(timezone.utc):%Y-%m-%d %H:%M}'})
    if not r.ok:
        return f'error {r.status_code}'
    bid = r.json().get('id')
    r2 = requests.post(f'https://api.resend.com/broadcasts/{bid}/send', headers=h, timeout=30, json={})
    return 'enviado' if r2.ok else f'error {r2.status_code}'


def main():
    r = check(session().get(f'{SITE}/api/fuentes/alertas-resumen', timeout=90))
    js = r.json()
    stations = (js.get('data') or {}).get('stations') or []
    if not stations:
        print('Sin datos del INA: no se cambia nada.'); return
    prev = load(STATE, {})
    first = not prev
    found = [] if first else changes(prev, stations)
    now = datetime.now(timezone.utc).isoformat(timespec='minutes')
    # sólo el nivel: así el archivo cambia (y la web se vuelve a publicar) únicamente cuando hay un cambio de nivel
    new_state = {s['id']: {'level': s.get('level')} for s in stations if s.get('level') in ORDER}
    if new_state != {k: {'level': v.get('level')} for k, v in prev.items()}:
        save(STATE, new_state)
    if first:
        print(f'Estado inicial guardado para {len(stations)} localidades.'); return
    if not found:
        print('Sin cambios de nivel.'); return
    msgs = [text(a) for a in found]
    worst = max(found, key=lambda a: ORDER[a['to']])
    head = f"{worst['place']} en {worst['to']}" + (f' y {len(found) - 1} cambio(s) más' if len(found) > 1 else '')
    tg, em, nt = telegram(msgs), email(msgs, head), ntfy(msgs, head)
    feed = load(FEED, {'items': []})
    for a, m in zip(found, msgs):
        feed['items'].insert(0, {**a, 'text': m, 'at': now})
    feed['items'] = feed['items'][:MAX_FEED]
    feed['updated'] = now
    save(FEED, feed)
    print(f'{len(found)} aviso(s). ntfy: {nt}. Telegram: {tg}. Correo: {em}.')
    for m in msgs:
        print(' -', m)


if __name__ == '__main__':
    sys.exit(main())
