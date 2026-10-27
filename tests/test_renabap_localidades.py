"""RENABAP por localidad: conteo sin red."""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("renabap_localidades", os.path.join(ROOT, "scripts", "renabap_localidades.py"))
rl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl)


def sq(lon, lat, d=0.002):
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]]}


def test_summarize_counts_nearby_barrios_and_families():
    pytest.importorskip("shapely")
    data = {"features": [
        {"geometry": sq(-58.84, -27.47), "properties": {"nombre_barrio": "Uno", "cantidad_familias_aproximada": "120"}},
        {"geometry": sq(-58.80, -27.44), "properties": {"nombre_barrio": "Dos", "cantidad_familias_aproximada": 30}},
        {"geometry": sq(-60.60, -32.95), "properties": {"nombre_barrio": "Lejos", "cantidad_familias_aproximada": 999}},
        {"geometry": None, "properties": {}}]}
    st = [{"id": "corrientes", "place": "Corrientes", "river": "Paraná", "lat": -27.46, "lon": -58.85},
          {"id": "asuncion", "place": "Asunción", "river": "Paraguay", "lat": -25.28, "lon": -57.65}]
    out = rl.summarize(data, st)
    c, a = out
    assert c["barrios"] == 2 and c["familias"] == 150 and c["mayores"][0]["nombre"] == "Uno"
    assert 8 < c["superficie_ha"] < 11       # dos cuadrados de ~200 m de lado
    assert a["barrios"] == 0 and a["familias"] is None


def test_pick_tolerates_renamed_fields():
    assert rl.pick({"Familias_estimadas": "12"}, "famil", numeric=True) == 12.0
    assert rl.pick({"x": 1}, "famil", numeric=True) is None


def test_services_reads_renamed_fields():
    out = rl.services({"agua_corriente": "Conexión irregular a la red", "efluente_cloacal": "Desagüe a pozo",
                       "energia_el": "Conexión irregular", "situa_domi": "Sin título", "ano_de_cre": "1998"})
    assert out["agua"].startswith("Conexión irregular") and out["cloaca"] == "Desagüe a pozo"
    assert out["electricidad"] == "Conexión irregular" and out["tenencia"] == "Sin título" and out["creacion"] == 1998
    assert rl.services({})["agua"] is None and rl.services({})["creacion"] is None
