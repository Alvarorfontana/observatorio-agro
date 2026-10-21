import json
from tools.import_nasa_power_point import convert

def test_power_preserves_point_and_missing_values(tmp_path):
    p=tmp_path/"power.json"
    p.write_text(json.dumps({"type":"Feature","geometry":{"type":"Point","coordinates":[-63.5,-38.5]},"properties":{"parameter":{"T2M":{"2026101300":15.4,"2026101301":-999},"PRECTOTCORR":{"2026101300":0.2}}}}))
    d=convert(p)
    assert d["source"]=="NASA POWER"
    assert d["kind"]=="point_observation"
    assert d["longitude"]==-63.5 and d["latitude"]==-38.5
    assert d["parameters"]["T2M"]["2026101300"]==15.4
    assert d["parameters"]["T2M"]["2026101301"] is None
