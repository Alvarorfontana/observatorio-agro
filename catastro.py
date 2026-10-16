"""catastro v1.0 — elegir el campo tocando la parcela del catastro (servicios públicos WFS provinciales).

Provincia de Buenos Aires: ARBA, servicio WFS de la IDE provincial (geo.arba.gov.ar, capa idera:Parcela), con la
nomenclatura catastral, la partida y la superficie. Córdoba: IDECOR (capa idecor:parcelas), con la nomenclatura y la
superficie. Salta (IDESA) y Neuquén (Catastro provincial) también publican sus parcelas. Municipios: Gualeguaychú (Entre Ríos);
en Buenos Aires, ARBA ya cubre todos los partidos. Santa Fe publica sus parcelas sólo como imagen (WMS). Paraguay: Servicio Nacional de
Catastro (snc:parcelas_activas). Brasil: Cadastro Ambiental Rural (SICAR, capa sicar_imoveis_<estado>), que es un
registro ambiental declarado por cada productor, no un catastro legal. Otras provincias se suman cuando publican un
servicio WFS abierto. Sólo se devuelven el límite, la nomenclatura y la superficie.
La parcela catastral es un límite legal: puede no coincidir con el alambrado ni con los lotes de uso.
"""
import math

import research_connectors as c

BR_UF = {'Acre': 'ac', 'Alagoas': 'al', 'Amapá': 'ap', 'Amazonas': 'am', 'Bahia': 'ba', 'Ceará': 'ce', 'Distrito Federal': 'df',
         'Espírito Santo': 'es', 'Goiás': 'go', 'Maranhão': 'ma', 'Mato Grosso': 'mt', 'Mato Grosso do Sul': 'ms', 'Minas Gerais': 'mg',
         'Pará': 'pa', 'Paraíba': 'pb', 'Paraná': 'pr', 'Pernambuco': 'pe', 'Piauí': 'pi', 'Rio de Janeiro': 'rj',
         'Rio Grande do Norte': 'rn', 'Rio Grande do Sul': 'rs', 'Rondônia': 'ro', 'Roraima': 'rr', 'Santa Catarina': 'sc',
         'São Paulo': 'sp', 'Sergipe': 'se', 'Tocantins': 'to'}

PROVIDERS = [
    {'id': 'arba', 'name': 'ARBA · Provincia de Buenos Aires', 'url': 'https://geo.arba.gov.ar/geoserver/idera/wfs',
     'layer': 'idera:Parcela', 'bbox': (-63.4, -41.1, -56.6, -33.2),
     'fields': lambda p: (p.get('cca'), p.get('pda'), p.get('tpa'), (p.get('ara1') or 0) / 1e4)},
    {'id': 'idecor', 'name': 'IDECOR · Provincia de Córdoba', 'url': 'https://idecor-ws.mapascordoba.gob.ar/geoserver/idecor/wfs',
     'layer': 'idecor:parcelas', 'bbox': (-65.8, -35.1, -61.7, -29.4),
     'fields': lambda p: (p.get('Nomenclatura'), p.get('Nomenclatura'), (p.get('Tipo_Parcela') or '').capitalize() or None,
                          ((p.get('Superficie_Tierra_Rural') or 0) + (p.get('Superficie_Tierra_Urbana') or 0)) / 1e4)},
    {'id': 'salta', 'name': 'IDESA · Provincia de Salta', 'url': 'https://geoportal.salta.gob.ar/geoserver/wfs',
     'layer': 'geonode:fc_parcelas_v20', 'bbox': (-68.6, -26.4, -62.3, -22.0),
     'fields': lambda p: (f"Dpto {p.get('departa')} · catastro {p.get('catastro')}" if p.get('catastro') else None, p.get('catastro'), None, None)},
    {'id': 'neuquen', 'name': 'Catastro · Provincia del Neuquén', 'url': 'https://catastro.neuquen.gov.ar/nqn_ide/services/IDE/Catastro/MapServer/WFSServer',
     'layer': 'Catastro:Parcelas', 'bbox': (-71.95, -41.1, -68.0, -36.1), 'format': 'GEOJSON',
     'fields': lambda p: (p.get('NOMENCLATURA') or p.get('NOMENCLA') or p.get('GmlID'), p.get('NOMENCLATURA') or p.get('OBJECTID'),
                          ', '.join(x for x in (p.get('LOCALIDAD'), p.get('DEPARTAMENTO')) if x) or None, None)},
    {'id': 'gualeguaychu', 'name': 'Municipio de Gualeguaychú (Entre Ríos)', 'url': 'https://geo.gualeguaychu.gov.ar/geoserver/ows',
     'layer': 'gis:parcelario', 'bbox': (-58.75, -33.12, -58.40, -32.90), 'municipal': True,
     'fields': lambda p: (f"Manzana {p.get('manz_1')} · parcela {p.get('parc_1')}" if p.get('manz_1') else None, None, 'Parcela urbana (catastro municipal)', None)},
    {'id': 'snc', 'name': 'Servicio Nacional de Catastro · Paraguay', 'url': 'https://www.catastro.gov.py/geoserver/snc/wfs',
     'layer': 'snc:parcelas_activas', 'bbox': (-62.7, -27.7, -54.2, -19.2),
     'fields': lambda p: (p.get('ccatastral'), p.get('padron'), 'Finca ' + str(p['finca']) if p.get('finca') else None, p.get('hectareas'))},
    {'id': 'sicar', 'name': 'Cadastro Ambiental Rural (SICAR) · Brasil', 'url': 'https://geoserver.car.gov.br/geoserver/sicar/wfs',
     'layer': 'sicar:sicar_imoveis_{uf}', 'bbox': (-74.0, -33.8, -34.7, 5.3), 'country': 'Brasil',
     'fields': lambda p: (p.get('cod_imovel'), p.get('cod_imovel'), 'Imóvel rural (CAR, declarado)', p.get('num_area'))},
]

# Jurisdicciones relevadas cuya parcela NO se puede leer como WFS abierto. No se consultan: quedan documentadas
# con su portal y contacto para pedir el acceso. Detalle completo y nota modelo en CATASTRO-FALTANTE.md.
PENDING = [
    {'jurisdiction': 'Santa Fe', 'org': 'IDESF', 'portal': 'https://www.santafe.gob.ar/idesf/', 'contact': 'idesf@santafe.gov.ar',
     'status': 'Las parcelas se publican sólo como imagen (WMS), no como vector.'},
    {'jurisdiction': 'Entre Ríos', 'org': 'IDEER · Catastro (ATER)', 'portal': 'https://geoservicios.entrerios.gov.ar/', 'contact': 'entrerios@ign.gob.ar',
     'status': 'Sin capa de parcelas abierta. Gualeguaychú (municipal) es la única excepción.'},
    {'jurisdiction': 'Corrientes', 'org': 'IDECorr', 'portal': 'https://ide.corrientes.gob.ar/', 'contact': 'idecorrientes@gmail.com',
     'status': 'Sin capa de parcelas abierta.'},
    {'jurisdiction': 'Misiones', 'org': 'IDE Misiones · DGC', 'portal': 'https://catastro.misiones.gov.ar/', 'contact': '',
     'status': 'Sin servicio abierto de parcelas.'},
    {'jurisdiction': 'Formosa', 'org': 'IDEF', 'portal': 'https://idef.formosa.gob.ar/', 'contact': 'idef@formosa.gov.ar',
     'status': 'Sin servicio abierto de parcelas.'},
    {'jurisdiction': 'Santiago del Estero', 'org': 'IDE Santiago · DGC', 'portal': 'https://www.idesantiago.gob.ar/', 'contact': 'direcciongeneraldecatastro@dgcsantiago.gob.ar',
     'status': 'Sin capa de parcelas abierta.'},
    {'jurisdiction': 'Chaco', 'org': 'IDE Chaco', 'portal': 'http://idechaco.gob.ar/', 'contact': 'chaco@ign.gob.ar',
     'status': 'La capa de parcelas existe, pero el servidor no responde.'},
    {'jurisdiction': 'La Pampa', 'org': 'IDELP · Catastro', 'portal': 'https://idelp.lapampa.gob.ar/', 'contact': 'catastro@lapampa.gob.ar',
     'status': 'La capa de parcelas existe, pero el servidor no responde.'},
    {'jurisdiction': 'Chubut', 'org': 'Sistema de Información Territorial (SIT)', 'portal': 'https://catastro.chubut.gov.ar/', 'contact': 'chubut@ign.gob.ar',
     'status': 'El servidor rechaza las conexiones.'},
    {'jurisdiction': 'Río Negro', 'org': 'IDE Río Negro · Catastro', 'portal': 'https://ide.rionegro.gov.ar/', 'contact': 'info.catastro@agencia.rionegro.gov.ar',
     'status': 'El servidor devuelve error.'},
    {'jurisdiction': 'Tucumán', 'org': 'IDET · DGC', 'portal': 'https://www.tucuman.gob.ar/organismos/direccion-general-de-catastro', 'contact': 'sistemas@dgc-tuc.gov.ar',
     'status': 'El servidor devuelve error.'},
    {'jurisdiction': 'Tierra del Fuego', 'org': 'IDETDF · Catastro (AREF)', 'portal': 'https://ide.tierradelfuego.gob.ar/', 'contact': 'catastrotdf@aref.gob.ar',
     'status': 'El servidor devuelve error.'},
    {'jurisdiction': 'Uruguay', 'org': 'IDEuy · Dirección Nacional de Catastro', 'portal': 'https://www.gub.uy/infraestructura-datos-espaciales/', 'contact': '',
     'status': 'Sin servicio abierto de padrones (la DNC publica sólo metadatos).'},
]


def _ha(ring):
    """Superficie aproximada de un anillo [[lat, lon]] en hectáreas."""
    lat0 = math.radians(sum(p[0] for p in ring) / len(ring))
    xy = [(math.radians(lo) * 6371008.8 * math.cos(lat0), math.radians(la) * 6371008.8) for la, lo in ring]
    return abs(sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1] for i in range(len(xy)))) / 2 / 1e4


def _rings(geom):
    t = geom.get('type'); cs = geom.get('coordinates') or []
    polys = [cs] if t == 'Polygon' else cs if t == 'MultiPolygon' else []
    return polys


def parcel_at(lat, lon):
    lat, lon = float(lat), float(lon)
    provs = [p for p in PROVIDERS if p['bbox'][0] <= lon <= p['bbox'][2] and p['bbox'][1] <= lat <= p['bbox'][3]]
    import focos
    country, state = focos.locate(lat, lon)
    resolved = []
    for p in provs:
        if p.get('country') == 'Brasil':
            if country != 'Brasil' or state not in BR_UF:
                continue
            p = {**p, 'layer': p['layer'].format(uf=BR_UF[state]), 'name': f"{p['name']} · {state}"}
        elif p['id'] == 'snc' and country != 'Paraguay':
            continue
        elif p['id'] in ('arba', 'idecor', 'salta', 'neuquen', 'gualeguaychu') and country not in (None, 'Argentina'):
            continue
        resolved.append(p)
    provs = resolved
    if not provs:
        return c.envelope(None, '', 'parcela del catastro', 'catastro provincial', 'sin dato',
                          'Por ahora el catastro está disponible en Buenos Aires, Córdoba, Salta, Neuquén y Gualeguaychú (Argentina), Paraguay y Brasil (CAR). Faltantes, contactos y pedido de acceso: ver CATASTRO-FALTANTE.md.')
    env = None
    for prov in provs:
        try:
            env = _query(prov, lat, lon)
        except Exception as e:   # un servicio caído o con TLS mal configurado no frena a los demás
            env = c.envelope(None, prov['url'], 'parcela del catastro', prov['name'], 'sin dato',
                             f"{prov['name']} no respondió ({type(e).__name__}: {str(e)[-220:]}).")
            continue
        if env.get('status') == 'recibido':
            return env
    return env


def _verify(prov):
    """car.gov.br usa un certificado intermedio de Sectigo que algunos entornos no traen: se agrega al paquete de certifi."""
    if prov['id'] != 'sicar':
        return True
    import certifi, os, tempfile
    path = os.path.join(tempfile.gettempdir(), 'dots_ca_car.pem')
    if not os.path.exists(path):
        extra = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs', 'car_gov_br_intermedio.pem')
        with open(path, 'w') as f:
            f.write(open(certifi.where()).read() + '\n' + open(extra).read())
    return path


_CAR_SESSION = None


def _session(prov):
    """car.gov.br sólo acepta cifrados TLS que OpenSSL 3 deja fuera por defecto: se habilitan para ese servidor
    (nivel de seguridad 1), sin dejar de verificar el certificado."""
    global _CAR_SESSION
    if prov['id'] != 'sicar':
        return c.SESSION
    if _CAR_SESSION is None:
        import ssl, requests
        from requests.adapters import HTTPAdapter

        class Legacy(HTTPAdapter):
            def init_poolmanager(self, *a, **k):
                ctx = ssl.create_default_context(cafile=_verify(prov))
                ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
                k['ssl_context'] = ctx
                return super().init_poolmanager(*a, **k)
        _CAR_SESSION = requests.Session()
        _CAR_SESSION.mount('https://geoserver.car.gov.br', Legacy())
    return _CAR_SESSION


def _query(prov, lat, lon):
    d = 0.0008
    r = _session(prov).get(prov['url'], timeout=25, verify=_verify(prov), params={
        'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': prov['layer'], 'outputFormat': prov.get('format', 'application/json'),
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
                try:
                    ha = float(ha) if ha else _ha(ring)
                except (TypeError, ValueError):
                    ha = _ha(ring)
                return c.envelope({'polygon': ring, 'nomenclature': nom or f.get('id'), 'partida': partida,
                                   'kind': kind, 'area_ha': round(ha, 2) or None,
                                   'provider': prov['name'],
                                   'note': ('Registro ambiental declarado por el productor (CAR), no un catastro legal.' if prov['id'] == 'sicar' else
                             'Límite catastral (legal): puede no coincidir con el alambrado ni con los lotes de uso.')},
                                  prov['url'], 'parcela del catastro', prov['name'])
    return c.envelope(None, prov['url'], 'parcela del catastro', prov['name'], 'sin dato', 'No hay una parcela del catastro en ese punto.')
