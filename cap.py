"""cap v1.0 — alertas DOTS en formato CAP 1.2 (Common Alerting Protocol, OASIS/WMO).

Traduce cada alerta de alerts.py a un mensaje CAP 1.2 (severidad, urgencia, certeza, categoría, área
y fuente) para publicar en agregadores CAP o enviar por push (ntfy/Apprise). No inventa datos: usa
los que ya evaluó alerts.py.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

NS = 'urn:oasis:names:tc:emergency:cap:1.2'
SEVERITY = {'alta': 'Severe', 'media': 'Moderate', 'baja': 'Minor'}
CATEGORY = {'fuego': 'Fire', 'helada': 'Met', 'calor': 'Met', 'lluvia': 'Met', 'sequia': 'Met', 'vegetacion': 'Met'}
DEFAULT_CATEGORY = 'Met'


def urgency(when, sent=None):
    """Immediate si el evento cae dentro de las próximas 24 h; si no, Expected."""
    if not when:
        return 'Expected'
    try:
        d = datetime.fromisoformat(str(when)[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return 'Expected'
    return 'Immediate' if -1 <= (d - (sent or datetime.now(timezone.utc))).days <= 1 else 'Expected'


def alert_to_info(alert, sent=None):
    """Alerta DOTS → bloque info de CAP 1.2."""
    return {'category': CATEGORY.get(alert.get('key'), DEFAULT_CATEGORY),
            'event': alert.get('title') or 'Alerta DOTS',
            'urgency': urgency(alert.get('when'), sent),
            'severity': SEVERITY.get(alert.get('level'), 'Unknown'),
            'certainty': 'Likely',
            'headline': alert.get('title') or 'Alerta DOTS',
            'description': alert.get('detail') or '',
            'instruction': alert.get('action') or '',
            'senderName': alert.get('source') or 'DOTS Campo'}


def to_xml(alerts, lat, lon, identifier=None, sender='DOTS Campo', radius_km=10, sent=None):
    """Lista de alertas DOTS + coordenadas → documento CAP 1.2 (string XML UTF-8)."""
    now = sent or datetime.now(timezone.utc)
    ident = identifier or f'DOTS-{now.strftime("%Y%m%d%H%M%S")}'
    root = ET.Element('alert', {'xmlns': NS})
    ET.SubElement(root, 'identifier').text = ident
    ET.SubElement(root, 'sender').text = sender
    ET.SubElement(root, 'sent').text = now.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    ET.SubElement(root, 'status').text = 'Actual'
    ET.SubElement(root, 'msgType').text = 'Alert'
    ET.SubElement(root, 'scope').text = 'Public'
    for a in alerts or []:
        i = alert_to_info(a, now)
        info = ET.SubElement(root, 'info')
        ET.SubElement(info, 'category').text = i['category']
        ET.SubElement(info, 'event').text = i['event']
        ET.SubElement(info, 'urgency').text = i['urgency']
        ET.SubElement(info, 'severity').text = i['severity']
        ET.SubElement(info, 'certainty').text = i['certainty']
        ET.SubElement(info, 'headline').text = i['headline']
        ET.SubElement(info, 'description').text = i['description']
        if i['instruction']:
            ET.SubElement(info, 'instruction').text = i['instruction']
        ET.SubElement(info, 'senderName').text = i['senderName']
        area = ET.SubElement(info, 'area')
        ET.SubElement(area, 'areaDesc').text = f'{lat:.5f}, {lon:.5f}'
        ET.SubElement(area, 'circle').text = f'{lat:.5f},{lon:.5f} {radius_km}'
    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
