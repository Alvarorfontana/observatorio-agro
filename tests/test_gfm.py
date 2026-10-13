"""Copernicus GFM: capas, última pasada, km² inundados y superposición (servicios simulados)."""
import os, sys
from datetime import date
from io import BytesIO
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import gfm

CAPS = b"""<?xml version="1.0"?><WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0"><Capability><Layer><Title>GFM</Title>
<Layer><Name>gfm:observed_flood_extent</Name><Title>Observed flood extent</Title><Dimension name="time">2015-01-01/2026-10-12/P1D</Dimension></Layer>
<Layer><Name>gfm:ensemble_likelihood</Name><Title>Likelihood</Title></Layer>
<Layer><Name>gfm:reference_water_mask</Name><Title>Reference water</Title></Layer>
</Layer></Capability></WMS_Capabilities>"""


def _png(frac, size=(100, 60)):
    from PIL import Image
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    w = int(size[0] * frac)
    for x in range(w):
        for y in range(size[1]):
            im.putpixel((x, y), (0, 0, 255, 255))
    b = BytesIO(); im.save(b, 'PNG'); return b.getvalue()


def test_capas_y_fechas():
    caps = gfm.parse_capabilities(CAPS)
    assert gfm.pick_layers(caps) == {'flood': 'gfm:observed_flood_extent', 'reference': 'gfm:reference_water_mask'}
    assert gfm.latest_time(caps['gfm:observed_flood_extent']['times'], date(2026, 10, 13)) == '2026-10-12'
    assert gfm.latest_time('2026-10-01,2026-10-05,2026-10-20', date(2026, 10, 13)) == '2026-10-05'


def test_agua_de_crecida_en_km2(monkeypatch):
    gfm._CAPS.update(t=0, v=None)
    class R:
        def __init__(self, content): self.content = content; self.ok = True
        def raise_for_status(self): pass
    def get(url, params=None, timeout=None):
        if params['request'] == 'GetCapabilities':
            return R(CAPS)
        assert params['time'] == '2026-10-11' and params['srs'] == 'EPSG:4326'
        return R(_png(0.2 if 'flood' in params['layers'] else 0.1))
    class J:
        def json(self): return {'features': [{'properties': {'sensing_date': '2026-10-11T09:10:00', 'flooded_pixels': 900}},
                                              {'properties': {'sensing_date': '2026-10-05T09:10:00', 'flooded_pixels': 0}}]}
    monkeypatch.setattr(gfm.c.SESSION, 'get', get)
    monkeypatch.setattr(gfm.c, '_post', lambda *a, **k: J())
    bbox = (-59.46, -29.25, -59.14, -29.03)
    f = gfm.flood_at(bbox, date(2026, 10, 13))
    total = gfm.area_km2(bbox)
    assert f['date'] == '2026-10-11' and f['age'] == 2 and f['passes'] == 2
    assert abs(f['flood_km2'] - 0.2 * total) < 0.5 and abs(f['water_km2'] - 0.1 * total) < 0.5
    out = gfm.overlay(_png(1.0, (90, 60)).replace(b'', b''), f['mask'])
    assert out[:8] == b'\x89PNG\r\n\x1a\n'


def test_informe_suma_gfm(monkeypatch):
    import cuenca as cc, cuenca_report as cr
    monkeypatch.setenv('DOTS_REPORT_IMAGERY', '1')
    s = next(x for x in cc.STATIONS if x['id'] == 'parana-goya')
    monkeypatch.setattr(gfm, 'flood_at', lambda bbox, today=None: {'date': '2026-10-11', 'age': 2, 'flood_km2': 37.4, 'flood_pct': 4.8,
                                                                  'water_km2': 120.0, 'box_km2': 780, 'mask': _png(0.3)})
    pic = {'image': list(_png(1.0, (100, 60))), 'bbox': (-59.46, -29.25, -59.14, -29.03)}
    f = cr.local_flood(s, pic, date(2026, 10, 13))
    assert f['ok'] and f['has_flood'] and f['overlaid'] and '37,4 km²' in f['summary']
    monkeypatch.setattr(gfm, 'flood_at', lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    f = cr.local_flood(s, None, date(2026, 10, 13))
    assert not f['ok'] and 'GFM' in f['missing']
