"""costs v1.0 — costos, logística y margen ganadero por lote.

Datos en vivo, todos abiertos y sin clave:
  * Distancia y tiempo por ruta: OSRM (Open Source Routing Machine, servidor público del proyecto,
    datos OpenStreetMap ODbL). Si no responde, distancia en línea recta × 1,3, marcada como estimada.
  * Ubicación del destino: Nominatim (OpenStreetMap). Respeta su política: User-Agent propio y pocas consultas.
  * Dólar: DolarAPI (oficial y mayorista); respaldo Bluelytics.

Lo que depende del establecimiento (precio de venta, costos, tarifa de flete) lo carga el usuario.
DOTS no inventa precios: si falta un valor, el resultado que lo necesita queda "sin dato".
"""
import math
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c

NOMINATIM = 'https://nominatim.openstreetmap.org/search'
OSRM = 'https://router.project-osrm.org/route/v1/driving'
DOLAR = 'https://dolarapi.com/v1/dolares'
BLUELYTICS = 'https://api.bluelytics.com.ar/v2/latest'
ROAD_FACTOR = 1.3   # sinuosidad típica de la red vial rural respecto de la línea recta

# Campos numéricos que puede cargar el usuario: (mínimo, máximo)
FIELDS = {
    'heads': (0, 200000), 'sale_kg': (20, 1200), 'price_kg': (0, 1e8), 'shrink_pct': (0, 15), 'commission_pct': (0, 15),
    'health_head': (0, 1e9), 'feed_head': (0, 1e9), 'other_head': (0, 1e9),
    'labor_month': (0, 1e10), 'rent_ha': (0, 1e9), 'structure_ha': (0, 1e9),
    'freight_km': (0, 1e7), 'truck_heads': (1, 200), 'area_ha': (0, 1e6),
}


def clean(params):
    out = {}
    for k, (lo, hi) in FIELDS.items():
        v = (params or {}).get(k)
        if v in (None, ''):
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ValueError(f'{k} inválido')
        if not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f'{k} fuera de rango ({lo}-{hi})')
        out[k] = v
    return out


def haversine_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def geocode(q):
    q = str(q or '').strip()
    if not 3 <= len(q) <= 160:
        raise ValueError('Escribí un destino (ciudad, remate, frigorífico o puerto)')
    r = c._get(NOMINATIM, {'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'ar,uy,py,br,bo,cl'}, timeout=15)
    hits = r.json()
    if not hits:
        raise ValueError(f'No se encontró "{q}" en OpenStreetMap')
    h = hits[0]
    return {'lat': float(h['lat']), 'lon': float(h['lon']), 'name': h.get('display_name', q)[:200]}


def route(origin, dest):
    """origin/dest = (lat, lon). Devuelve km, horas, geometría simplificada y método."""
    try:
        r = c._get(f'{OSRM}/{origin[1]:.5f},{origin[0]:.5f};{dest[1]:.5f},{dest[0]:.5f}',
                   {'overview': 'simplified', 'geometries': 'geojson'}, timeout=20)
        js = r.json()
        rt = (js.get('routes') or [None])[0]
        if js.get('code') == 'Ok' and rt:
            line = [[round(lat, 5), round(lon, 5)] for lon, lat in (rt.get('geometry') or {}).get('coordinates') or []]
            return {'km': round(rt['distance'] / 1000, 1), 'hours': round(rt['duration'] / 3600, 2), 'line': line,
                    'method': 'ruta por camino (OSRM · OpenStreetMap)', 'estimated': False}
    except Exception:
        pass
    km = haversine_km(origin, dest) * ROAD_FACTOR
    return {'km': round(km, 1), 'hours': None, 'line': [list(origin), list(dest)],
            'method': f'estimada: línea recta × {ROAD_FACTOR} (el servicio de rutas no respondió)', 'estimated': True}


def exchange():
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fo = pool.submit(c._get, f'{DOLAR}/oficial', None, None, 12)
            fm = pool.submit(c._get, f'{DOLAR}/mayorista', None, None, 12)
            o = fo.result().json()
            try:
                m = fm.result().json()
            except Exception:
                m = {}
        return {'oficial_venta': o.get('venta'), 'oficial_compra': o.get('compra'), 'mayorista_venta': m.get('venta'),
                'updated': o.get('fechaActualizacion'), 'source': 'DolarAPI'}
    except Exception:
        js = c._get(BLUELYTICS, timeout=12).json()
        o = js.get('oficial') or {}
        return {'oficial_venta': o.get('value_sell'), 'oficial_compra': o.get('value_buy'), 'mayorista_venta': None,
                'updated': js.get('last_update'), 'source': 'Bluelytics'}


def margin(p, km=None):
    """Margen bruto ganadero simple. p = clean(params). Cada línea sin datos queda en None."""
    heads, area = p.get('heads'), p.get('area_ha')
    sold_kg = heads * p['sale_kg'] * (1 - p.get('shrink_pct', 0) / 100) if heads and p.get('sale_kg') else None
    gross = sold_kg * p['price_kg'] if sold_kg is not None and p.get('price_kg') is not None else None
    commission = gross * p.get('commission_pct', 0) / 100 if gross is not None else None
    per_head = sum(p.get(k, 0) for k in ('health_head', 'feed_head', 'other_head'))
    direct = (per_head * heads if heads else 0) + p.get('labor_month', 0) * 12
    land = (p.get('rent_ha', 0) + p.get('structure_ha', 0)) * area if area else 0
    trips = math.ceil(heads / p['truck_heads']) if heads and p.get('truck_heads') else None
    freight = trips * km * p['freight_km'] if trips and km is not None and p.get('freight_km') is not None else None
    costs = direct + land + (commission or 0) + (freight or 0)
    net = gross - costs if gross is not None else None
    breakeven = (direct + land + (freight or 0)) / (sold_kg * (1 - p.get('commission_pct', 0) / 100)) if sold_kg else None
    lines = [
        ('Ingreso bruto', gross), ('Comisión de venta', -commission if commission is not None else None),
        ('Sanidad, alimentación y otros por cabeza', -per_head * heads if heads and per_head else None),
        ('Mano de obra (12 meses)', -p['labor_month'] * 12 if p.get('labor_month') else None),
        ('Arrendamiento y estructura', -land if land else None), ('Flete', -freight if freight is not None else None),
    ]
    return {
        'kg_sold': round(sold_kg, 0) if sold_kg is not None else None, 'gross': _r(gross), 'costs': _r(costs),
        'net': _r(net), 'net_ha': _r(net / area) if net is not None and area else None,
        'net_head': _r(net / heads) if net is not None and heads else None,
        'breakeven_price_kg': _r(breakeven, 1), 'trips': trips, 'freight': _r(freight),
        'freight_per_head': _r(freight / heads) if freight is not None and heads else None,
        'freight_per_kg': _r(freight / sold_kg, 2) if freight is not None and sold_kg else None,
        'lines': [{'label': l, 'value': _r(v)} for l, v in lines if v is not None],
    }


def sensitivity(p, km):
    """Margen total con precio −20 %…+20 % y flete actual / +25 %."""
    if not (p.get('price_kg') and p.get('heads') and p.get('sale_kg')):
        return None
    rows = []
    for f in (0.8, 0.9, 1.0, 1.1, 1.2):
        q = dict(p, price_kg=p['price_kg'] * f)
        a = margin(q, km)['net']
        b = margin(dict(q, freight_km=p['freight_km'] * 1.25), km)['net'] if p.get('freight_km') is not None else None
        rows.append({'price_factor': f, 'price_kg': _r(q['price_kg'], 1), 'net': a, 'net_freight_up': b})
    return rows


def _r(v, n=0):
    return None if v is None else round(v, n) if n else round(v)


def analyze(lat, lon, destination=None, dest_lat=None, dest_lon=None, params=None):
    p = clean(params)
    errors, logistics, fx = {}, None, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        ffx = pool.submit(exchange)
        try:
            if dest_lat is not None and dest_lon is not None:
                d = {'lat': float(dest_lat), 'lon': float(dest_lon), 'name': str(destination or 'Destino')[:200]}
                c.coordinates({'lat': [d['lat']], 'lon': [d['lon']]})
            elif destination:
                d = geocode(destination)
            else:
                d = None
            if d:
                logistics = {'destination': d, **route((lat, lon), (d['lat'], d['lon']))}
        except ValueError as e:
            errors['destino'] = str(e)
        except Exception as e:
            errors['destino'] = f'No se pudo ubicar el destino ({type(e).__name__})'
        try:
            fx = ffx.result()
        except Exception as e:
            errors['dólar'] = type(e).__name__
    km = logistics['km'] if logistics else None
    m = margin(p, km)
    usd = fx.get('oficial_venta') if fx else None
    if usd:
        m['net_ha_usd'] = round(m['net_ha'] / usd, 1) if m.get('net_ha') is not None else None
        m['net_usd'] = round(m['net'] / usd) if m.get('net') is not None else None
        m['breakeven_usd_kg'] = round(m['breakeven_price_kg'] / usd, 2) if m.get('breakeven_price_kg') else None
    missing = [lab for k, lab in (('heads', 'cabezas'), ('sale_kg', 'peso de venta'), ('price_kg', 'precio por kg'))
               if k not in p]
    if logistics and 'freight_km' not in p:
        missing.append('tarifa de flete por km')
    out = {
        'capability': 'ANALYSIS', 'inputs': p, 'logistics': logistics, 'exchange': fx, 'margin': m,
        'sensitivity': sensitivity(p, km), 'missing': missing, 'errors': errors,
        'method': ('Margen bruto = kg vendidos × precio − comisión − costos por cabeza − mano de obra − arrendamiento y estructura − flete. '
                   'kg vendidos = cabezas × peso × (1 − desbaste). Flete = viajes × km × tarifa por km; viajes = cabezas ÷ capacidad de la jaula. '
                   'Precio de equilibrio = costos sin comisión ÷ kg netos de comisión.'),
        'scope': ('Valores cargados por el usuario; DOTS sólo aporta distancia, tiempo de viaje y tipo de cambio en vivo. '
                  'Referencias de precios: Mercado Agroganadero de Cañuelas e índices de la Bolsa; tarifas de flete: CATAC.'),
    }
    ok = bool(logistics or fx or m.get('gross') is not None)
    return c.envelope(out, OSRM, 'costos, logística y margen', 'OSRM · OpenStreetMap · DolarAPI · DOTS',
                      'recibido' if ok else 'sin dato', None if ok else 'Cargá al menos un destino o los datos de venta')
