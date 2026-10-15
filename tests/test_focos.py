import json
import focos as fz

MODIS = "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight\n-27.5,-58.8,320.1,1,1,2026-10-14,1244,T,MODIS,70,6.1NRT,295,12.4,D\n-40.0,-50.0,320,1,1,2026-10-14,0310,A,MODIS,50,6.1NRT,290,3,N\n"
VIIRS = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n-34.6,-58.4,330,0.4,0.4,2026-10-15,0405,N,VIIRS,h,2.0NRT,290,5.5,N\n"


def test_parse_and_locate():
    rows = fz.parse_csv(MODIS, 'MODIS (Terra/Aqua)') + fz.parse_csv(VIIRS, 'VIIRS Suomi NPP')
    assert rows[0]['time'] == '12:44' and rows[0]['dn'] == 'día' and rows[2]['conf'] == 'alta'
    for r in rows:
        r['country'], r['province'] = fz.locate(r['lat'], r['lon'])
    assert rows[0]['province'] == 'Corrientes' and rows[1]['country'] is None
    prov = fz.summarize([r for r in rows if r['country']])
    assert prov[0]['count'] == 1 and 'focos' in fz.reading([r for r in rows if r['country']], prov, 2)
    csv = fz.to_csv(rows)
    assert csv.splitlines()[0].startswith('lat,lon,date') and 'Corrientes' in csv


def test_enrich_expression():
    body = json.dumps(fz.enrich_expression([(0, {'lat': -27.5, 'lon': -58.8}), (5, {'lat': -30, 'lon': -60})]))
    assert 'ESA/WorldCover/v200' in body and 'WCMC/WDPA/current/polygons' in body and 'sampleRegions' in body


def test_route_without_key(monkeypatch):
    from flask import Flask
    from research_routes import research_api
    monkeypatch.delenv('FIRMS_MAP_KEY', raising=False)
    fz._CACHE.clear()
    app = Flask(__name__); app.register_blueprint(research_api)
    r = app.test_client().get('/api/fuentes/focos?dias=2')
    assert r.status_code == 409 and 'FIRMS_MAP_KEY' in r.get_json()['error']
