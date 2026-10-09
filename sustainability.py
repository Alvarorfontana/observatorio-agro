"""sustainability v3.0 — libre de deforestación, carbono del suelo y emisiones del rodeo.

Deforestación (referencia EUDR, fecha de corte 31/12/2020):
  * Impact Observatory 10 m Annual LULC v2 (2017-2023, CC-BY-4.0), Planetary Computer,
    colección io-lulc-annual-v02, asset `data`, clase 2 = árboles.
  * ESA WorldCover 10 m 2020 y 2021 (CC-BY-4.0), colección esa-worldcover, asset `map`, clase 10.
  Se mide la fracción del lote con árboles cada año y se compara el último año con 2020.
  Es una verificación de cobertura por teledetección, no una certificación legal: la debida
  diligencia EUDR exige además georreferencia oficial, trazabilidad y revisión humana.

Carbono del suelo: ISRIC SoilGrids `ocs` (stock de carbono orgánico 0-30 cm, t/ha).
Emisiones del rodeo: IPCC 2006 Nivel 1, fermentación entérica de "otros bovinos" en
Latinoamérica = 56 kg CH4/cabeza/año (Vol. 4, Cap. 10, cuadro 10.11), GWP100 del metano
no fósil = 27 (IPCC AR6). Ambos parámetros se informan y pueden ajustarse.
"""
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c
import vegetation as veg

PC_STAC = veg.PC_STAC
PC_DATA = veg.PC_DATA
CUTOFF_YEAR = 2020
EF_CH4_HEAD = 56.0      # kg CH4 / cabeza / año (IPCC 2006, Latinoamérica, otros bovinos)
GWP_CH4 = 27.0          # IPCC AR6, metano no fósil, horizonte 100 años
C_TO_CO2 = 44 / 12


def _items(collection, geom, year):
    body = {'collections': [collection], 'intersects': geom, 'limit': 5,
            'datetime': f'{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z'}
    return c._post(PC_STAC + '/search', body, timeout=30).json().get('features', [])


def _fraction(collection, item_id, asset, value, feature):
    r = c.SESSION.post(f'{PC_DATA}/item/statistics',
                       params={'collection': collection, 'item': item_id,
                               'expression': f'where({asset}=={value},1,0)', 'asset_as_band': 'true'},
                       json=feature, timeout=40)
    r.raise_for_status()
    return veg._first_stats(r.json()).get('mean')


def _year_cover(collection, asset, classes, year, geom, feature):
    items = _items(collection, geom, year)
    if not items:
        return None
    it = items[0]
    out = {'year': year, 'item': it['id']}
    for key, val in classes.items():
        v = _fraction(collection, it['id'], asset, val, feature)
        out[key] = None if v is None else round(float(v), 4)
    return out


def deforestation(polygon):
    pts = veg.require_polygon(polygon)
    geom = veg.geojson_polygon(pts)
    feature = {'type': 'Feature', 'properties': {}, 'geometry': geom}
    area = veg.area_ha(pts)
    io_years = list(range(2017, 2024))
    io_classes = {'trees': 2, 'rangeland': 11, 'crops': 5, 'water': 1, 'flooded': 4}
    with ThreadPoolExecutor(max_workers=4) as pool:
        io_f = {y: pool.submit(_year_cover, 'io-lulc-annual-v02', 'data', io_classes, y, geom, feature) for y in io_years}
        wc_f = {y: pool.submit(_year_cover, 'esa-worldcover', 'map', {'trees': 10, 'grass': 30, 'crops': 40}, y, geom, feature)
                for y in (2020, 2021)}
        io, wc, errors = [], [], {}
        for y, f in io_f.items():
            try:
                r = f.result()
                if r: io.append(r)
            except Exception as e:
                errors[f'io-{y}'] = type(e).__name__
        for y, f in wc_f.items():
            try:
                r = f.result()
                if r: wc.append(r)
            except Exception as e:
                errors[f'wc-{y}'] = type(e).__name__
    io.sort(key=lambda r: r['year'])
    base = next((r for r in io if r['year'] == CUTOFF_YEAR and r.get('trees') is not None), None)
    last = next((r for r in reversed(io) if r.get('trees') is not None), None)
    verdict, loss_ha, change_pp = 'sin dato', None, None
    if base and last and last['year'] > CUTOFF_YEAR:
        change_pp = round((last['trees'] - base['trees']) * 100, 2)
        loss_ha = round(max(0.0, (base['trees'] - last['trees'])) * area, 2)
        if loss_ha < 0.5 or change_pp > -1:
            verdict = 'sin pérdida de cobertura arbórea detectada'
        elif loss_ha < 5:
            verdict = 'pérdida menor detectada · revisar'
        else:
            verdict = 'pérdida de cobertura arbórea detectada · requiere verificación'
    wc_trees = {r['year']: r.get('trees') for r in wc}
    ok = bool(io or wc)
    return c.envelope({
        'capability': 'ANALYSIS', 'area_ha': area, 'cutoff': f'31/12/{CUTOFF_YEAR}',
        'verdict': verdict, 'tree_change_pp': change_pp, 'tree_loss_ha': loss_ha,
        'baseline_year': base['year'] if base else None, 'last_year': last['year'] if last else None,
        'series': io, 'worldcover': wc, 'worldcover_tree_2020': wc_trees.get(2020), 'worldcover_tree_2021': wc_trees.get(2021),
        'errors': errors,
        'scope': ('Verificación de cobertura por teledetección a 10 m (Impact Observatory 2017-2023 y ESA WorldCover 2020-2021). '
                  'No es una certificación legal: la debida diligencia de la Unión Europea exige además documentación, trazabilidad y revisión.')},
        PC_DATA + '/item/statistics', 'cobertura arbórea del lote 2017-2023', 'Impact Observatory · ESA · Microsoft Planetary Computer',
        'recibido' if ok else 'sin dato', None if ok else 'No hubo datos de cobertura para el lote')


def carbon(lat, lon, area_ha=None, heads=None, ef=EF_CH4_HEAD, gwp=GWP_CH4):
    env = c.external('https://rest.isric.org/soilgrids/v2.0/properties/query',
                     {'lat': lat, 'lon': lon, 'property': 'ocs', 'depth': '0-30cm', 'value': ['Q0.05', 'mean', 'Q0.95']},
                     scope='stock de carbono orgánico del suelo 0-30 cm', organism='ISRIC SoilGrids')
    soc = lo = hi = None
    for layer in ((env['data'] or {}).get('properties') or {}).get('layers') or []:
        if layer.get('name') != 'ocs':
            continue
        f = (layer.get('unit_measure') or {}).get('d_factor') or 1
        vals = ((layer.get('depths') or [{}])[0].get('values') or {})
        to = lambda k: None if vals.get(k) is None else round(vals[k] / f, 1)
        soc, lo, hi = to('mean'), to('Q0.05'), to('Q0.95')
    out = {'soc_t_ha': soc, 'soc_t_ha_range': [lo, hi], 'unit': 't C/ha (0-30 cm)'}
    if soc is not None and area_ha:
        out['soc_total_t'] = round(soc * area_ha, 0)
        out['soc_total_tco2e'] = round(soc * area_ha * C_TO_CO2, 0)
    if heads:
        heads = max(0, int(heads))
        ch4 = heads * ef / 1000
        out['herd'] = {'heads': heads, 'ch4_t_year': round(ch4, 1), 'co2e_t_year': round(ch4 * gwp, 1),
                       'per_head_co2e_t': round(ef * gwp / 1000, 2), 'ef_kg_ch4_head': ef, 'gwp': gwp,
                       'method': 'IPCC 2006 Nivel 1 (fermentación entérica, otros bovinos, Latinoamérica) · GWP100 AR6'}
        if out.get('soc_total_tco2e'):
            out['herd']['years_equiv_soc'] = round(out['soc_total_tco2e'] / max(ch4 * gwp, 1e-9), 0)
    out['scope'] = ('El stock de carbono del suelo es un modelo global a 250 m: sirve de línea de base, no reemplaza el muestreo '
                    'que exige un proyecto de bonos de carbono. Las emisiones usan factores por defecto del IPCC.')
    return c.envelope(out, env['source_url'], 'carbono del suelo y emisiones del rodeo', 'ISRIC SoilGrids · IPCC')


IO_COLORS = {0: [0, 0, 0, 0], 1: [65, 155, 223, 255], 2: [57, 125, 73, 255], 4: [122, 135, 198, 255], 5: [228, 150, 53, 255],
             7: [196, 40, 27, 255], 8: [165, 155, 143, 255], 9: [168, 235, 255, 255], 10: [97, 97, 97, 255], 11: [227, 226, 195, 255]}
IO_LEGEND = [('#397d49', 'Árboles'), ('#e3e2c3', 'Pastizal'), ('#e49635', 'Cultivo'), ('#419bdf', 'Agua'),
             ('#7a87c6', 'Vegetación inundada'), ('#a59b8f', 'Suelo desnudo'), ('#c4281b', 'Construido')]


def cover_png(item_id, polygon):
    """PNG de la cobertura anual (Impact Observatory) recortada al lote, con los colores oficiales de las clases."""
    import json as _json
    pts = veg.require_polygon(polygon)
    if not isinstance(item_id, str) or not 3 <= len(item_id) <= 80 or not all(ch.isalnum() or ch in '-_.' for ch in item_id):
        raise ValueError('Ítem de cobertura inválido')
    feature = {'type': 'Feature', 'properties': {}, 'geometry': veg.geojson_polygon(pts)}
    r = c.SESSION.post(f'{PC_DATA}/item/feature.png',
                       params={'collection': 'io-lulc-annual-v02', 'item': item_id, 'assets': 'data', 'asset_bidx': 'data|1',
                               'colormap': _json.dumps({str(k): v for k, v in IO_COLORS.items()}), 'max_size': 768},
                       json=feature, timeout=40)
    r.raise_for_status()
    if not r.headers.get('Content-Type', '').startswith('image/png'):
        raise ValueError('La API raster no devolvió PNG')
    w, s, e, n = c.polygon_bbox(pts)
    return r.content, [[s, w], [n, e]]
