import csv
from tools.validate_ina_levels import read_levels

def test_station_directory_is_not_hydrometric_measurement(tmp_path):
    p=tmp_path/"ina.csv"
    p.write_text("estacion,fecha_consulta,nota\nCorrientes,2026-10-21,encontrado_en_HTML\n")
    d=read_levels(p)
    assert d["status"]=="no_measurements"
    assert d["stations"]==["Corrientes"]
    assert d["observations"]==[]

def test_valid_measurement_is_parsed(tmp_path):
    p=tmp_path/"levels.csv"
    p.write_text("estacion,fecha_medicion,altura_m\nCorrientes,2026-10-20T10:00,4.12\n")
    d=read_levels(p)
    assert d["status"]=="observed"
    assert d["observations"][0]["level_m"]==4.12
