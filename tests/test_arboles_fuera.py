import json

import arboles_fuera as af

LOTE = [[-28.50, -59.05], [-28.50, -59.03], [-28.52, -59.03], [-28.52, -59.05]]


def _funcs(node, out):
    if isinstance(node, dict):
        f = node.get('functionInvocationValue')
        if f:
            out.add(f['functionName'])
        for v in node.values():
            _funcs(v, out)
    elif isinstance(node, list):
        for v in node:
            _funcs(v, out)
    return out


def test_expresion_cruza_worldcover_y_jrc():
    e = af.expression(LOTE)
    txt = json.dumps(e)
    assert af.WC in txt and af.JRC in txt
    fs = _funcs(e, set())
    assert {'Image.connectedPixelCount', 'Image.reduceRegion', 'Image.pixelArea', 'Image.not', 'Image.and'} <= fs
    out = e['expression']['values']['out']['functionInvocationValue']['arguments']
    assert out['scale'] == {'constantValue': 10}


def test_imagen_del_lote():
    body, bounds = af.png_expression(LOTE)
    s, w, n, e = bounds
    assert s < -28.52 and n > -28.50 and w < -59.05 and e > -59.03
    g = body['grid']
    assert body['fileFormat'] == 'PNG' and g['dimensions']['width'] == af.PNG_PX and g['affineTransform']['scaleY'] < 0


def test_resumen_y_lectura():
    d = af.summarize({'forest': 12.0, 'inside': 10.0, 'small': 3.2, 'large': 1.5}, 100)
    assert d['trees_ha'] == 14.7 and d['outside_ha'] == 4.7 and d['outside_pct'] == 4.7
    assert 'cortinas' in d['reading'] and 'Ley 26.331' in d['reading']
    assert af.summarize({}, 50)['reading'].startswith('El mapa no registra')
    solo = af.summarize({'forest': 8, 'inside': 6}, 50)
    assert solo['outside_ha'] == 0 and 'dentro del bosque' in solo['reading']


def test_ruta_y_bloque_del_informe():
    import research_routes as rr
    import report_typst as rt
    assert 'arboles-fuera' in rr.VEGETATION
    b = rt._tof_block(af.summarize({'forest': 12.0, 'inside': 10.0, 'small': 3.2, 'large': 1.5}, 100))
    assert len(b['rows']) == 4 and b['rows'][2][1] == '3,2 ha'
    assert rt._tof_block(None) is None
