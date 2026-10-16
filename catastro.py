"""catastro v1.0 — elegir el campo tocando la parcela del catastro (servicios públicos WFS provinciales).

Provincia de Buenos Aires: ARBA, servicio WFS de la IDE provincial (geo.arba.gov.ar, capa idera:Parcela), con la
nomenclatura catastral, la partida y la superficie. Otras provincias se suman cuando publican un servicio WFS abierto.
La parcela catastral es un límite legal: puede no coincidir con el alambrado ni con los lotes de uso.
"""
import research_connectors as c

PROVIDERS = [
    {'id': 'arba', 'name': 'ARBA · Provincia de Buenos Aires', 'url': 'https://geo.arba.gov.ar/geoserver/idera/wfs',
     'layer': 'idera:Parcela', 'bbox': (-63.4, -41.1, -56.6, -33.2)},
]


def _rings(geom):
    t = geom.get('type'); cs = geom.get('coordinates') or []
    polys = [cs] if t == 'Polygon' else cs if t == 'MultiPolygon' else []
    return polys


def parcel_at(lat, lon):
    lat, lon = float(lat), float(lon)
    prov = next((p for p in PROVIDERS if p['bbox'][0] <= lon <= p['bbox'][2] and p['bbox'][1] <= lat <= p['bbox'][3]), None)
    if not prov:
        return c.envelope(None, '', 'parcela del catastro', 'catastro provincial', 'sin dato',
                          'Por ahora el catastro está disponible para la provincia de Buenos Aires (ARBA).')
    d = 0.0008
    r = c.SESSION.get(prov['url'], timeout=25, params={
        'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': prov['layer'], 'outputFormat': 'application/json',
        'srsName': 'EPSG:4326', 'count': 20, 'bbox': f'{lat - d},{lon - d},{lat + d},{lon + d},urn:ogc:def:crs:EPSG::4326'})
    r.raise_for_status()
    feats = r.json().get('features') or []
    for f in feats:
        for poly in _rings(f.get('geometry') or {}):
            ring = [[y, x] for x, y in poly[0]]
            if c.point_in_polygon(lat, lon, ring):
                p = f.get('properties') or {}
                if ring and ring[0] == ring[-1]:
                    ring = ring[:-1]
                return c.envelope({'polygon': ring, 'nomenclature': p.get('cca') or f.get('id'), 'partida': p.get('pda'),
                                   'kind': p.get('tpa'), 'area_ha': round((p.get('ara1') or 0) / 1e4, 2) or None,
                                   'provider': prov['name'],
                                   'note': 'Límite catastral (legal): puede no coincidir con el alambrado ni con los lotes de uso.'},
                                  prov['url'], 'parcela del catastro', prov['name'])
    return c.envelope(None, prov['url'], 'parcela del catastro', prov['name'], 'sin dato', 'No hay una parcela del catastro en ese punto.')
