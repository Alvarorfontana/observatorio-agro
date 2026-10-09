"""contact v2.9 — canal de consultas del sitio.

Envía cada consulta por correo con Resend (https://resend.com, plan gratuito) cuando están
configuradas en Vercel:
  RESEND_API_KEY   clave de Resend
  CONTACT_TO       correo que recibe las consultas
  CONTACT_FROM     remitente verificado (opcional; por defecto onboarding@resend.dev,
                   que sólo entrega al correo dueño de la cuenta Resend)
  CONTACT_WHATSAPP número público para el botón de WhatsApp, con código de país (opcional)
Nunca se expone CONTACT_TO al navegador. Si no hay canal configurado se informa y no se
simula el envío.
"""
import os, re

import research_connectors as c

TOPICS = {'consulta': 'Consulta general', 'demo': 'Pedido de demostración', 'soporte': 'Soporte técnico',
          'sugerencia': 'Sugerencia o inquietud', 'alianza': 'Alianza o institución'}
EMAIL = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$')


def channel():
    wa = re.sub(r'\D', '', os.environ.get('CONTACT_WHATSAPP', ''))
    return {'email_enabled': bool(os.environ.get('RESEND_API_KEY') and os.environ.get('CONTACT_TO')),
            'whatsapp': wa if 8 <= len(wa) <= 15 else None, 'topics': TOPICS}


def validate(d):
    if (d.get('website') or '').strip():          # campo trampa para robots
        raise ValueError('Envío rechazado')
    name = str(d.get('nombre') or '').strip()
    email = str(d.get('correo') or '').strip()
    msg = str(d.get('mensaje') or '').strip()
    topic = str(d.get('tema') or 'consulta')
    org = str(d.get('establecimiento') or '').strip()[:120]
    phone = re.sub(r'[^\d+ ()-]', '', str(d.get('telefono') or ''))[:30]
    if not 2 <= len(name) <= 100:
        raise ValueError('Escribí tu nombre')
    if not EMAIL.match(email):
        raise ValueError('El correo no parece válido')
    if not 10 <= len(msg) <= 4000:
        raise ValueError('Contanos tu consulta (entre 10 y 4000 caracteres)')
    if topic not in TOPICS:
        topic = 'consulta'
    return {'nombre': name, 'correo': email, 'mensaje': msg, 'tema': topic, 'establecimiento': org, 'telefono': phone}


def send(d):
    data = validate(d)
    key, to = os.environ.get('RESEND_API_KEY'), os.environ.get('CONTACT_TO')
    if not key or not to:
        raise PermissionError('El canal de correo todavía no está configurado')
    body = '\n'.join([f"Tema: {TOPICS[data['tema']]}", f"Nombre: {data['nombre']}", f"Correo: {data['correo']}",
                      f"Teléfono: {data['telefono'] or '—'}", f"Establecimiento / organización: {data['establecimiento'] or '—'}",
                      '', data['mensaje'], '', '— Enviado desde el formulario de DOTS / Campo'])
    r = c.SESSION.post('https://api.resend.com/emails', timeout=20, headers={'Authorization': f'Bearer {key}'},
                       json={'from': os.environ.get('CONTACT_FROM') or 'DOTS Campo <onboarding@resend.dev>',
                             'to': [to], 'reply_to': data['correo'],
                             'subject': f"[DOTS] {TOPICS[data['tema']]} · {data['nombre']}", 'text': body})
    r.raise_for_status()
    return {'status': 'enviado', 'id': (r.json() or {}).get('id')}
