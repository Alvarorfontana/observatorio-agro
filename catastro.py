"""catastro v1.0 — elegir el campo tocando la parcela del catastro (servicios públicos WFS provinciales).

Provincia de Buenos Aires: ARBA, servicio WFS de la IDE provincial (geo.arba.gov.ar, capa idera:Parcela), con la
nomenclatura catastral, la partida y la superficie. Córdoba: IDECOR (capa idecor:parcelas), con la nomenclatura y la
superficie. Santa Fe publica sus parcelas sólo como imagen (WMS), sin el límite descargable. Otras provincias se suman
cuando publican un servicio WFS abierto. Sólo se devuelven el límite, la nomenclatura y la superficie.
La parcela catastral es un límite legal: puede no coincidir con el alambrado ni con los lotes de uso.
"""
import research_connectors as c

PROVIDERS = [
    {'id': 'arba', 'name': 'ARBA · Provincia de Buenos Aires', 'url': 'https://geo.arba.gov.ar/geoserver/idera/wfs',
     'layer': 'idera:Parcela', 'bbox': (-63.4, -41.1, -56.6, -33.2),
     'fields': lambda p: (p.get('cca'), p.get('pda'), p.get('tpa'), (p.get('ara1') or 0) / 1e4)},
    {'id': 'idecor', 'name': 'IDECOR · Provincia de Córdoba', 'url': 'https://idecor-ws.mapascordoba.gob.ar/geoserver/idecor/wfs',
     'layer': 'idecor:parcelas', 'bbox': (-65.8, -35.1, -61.7, -29.4),
     'fields': lambda p: (p.get('Nomenclatura'), p.get('Nomenclatura'), (p.get('Tipo_Parcela') or '').capitalize() or None,
                          ((p.get('Superficie_Tierra_Rural') or 0) + (p.get('Superficie_Tierra_Urbana') or 0)) / 1e4)},
]


def _rings(geom):
    t = geom.get('type'); cs = geom.get('coordinates') or []
    polys = [cs] if t == 'Polygon' else cs if t == 'MultiPolygon' else []
    return polys


def parcel_at(lat, lon):
    lat, lon = float(lat), float(lon)
    provs = [p for p in PROVIDERS if p['bbox'][0] <= lon <= p['bbox'][2] and p['bbox'][1] <= lat <= p['bbox'][3]]
    if not provs:
        return c.envelope(None, '', 'parcela del catastro', 'catastro provincial', 'sin dato',
                          'Por ahora el catastro está disponible para las provincias de Buenos Aires (ARBA) y Córdoba (IDECOR).')
    for prov in provs:
        env = _query(prov, lat, lon)
        if env.get('status') == 'recibido':
            return env
    return env


def _query(prov, lat, lon):
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
                nom, partida, kind, ha = prov['fields'](f.get('properties') or {})
                if ring and ring[0] == ring[-1]:
                    ring = ring[:-1]
                return c.envelope({'polygon': ring, 'nomenclature': nom or f.get('id'), 'partida': partida,
                                   'kind': kind, 'area_ha': round(ha, 2) or None,
                                   'provider': prov['name'],
                                   'note': 'Límite catastral (legal): puede no coincidir con el alambrado ni con los lotes de uso.'},
                                  prov['url'], 'parcela del catastro', prov['name'])
    return c.envelope(None, prov['url'], 'parcela del catastro', prov['name'], 'sin dato', 'No hay una parcela del catastro en ese punto.')
