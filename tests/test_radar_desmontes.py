"""Confirmación por radar de desmontes: partes que no necesitan red ni Earth Engine."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("radar_desmontes", os.path.join(ROOT, "scripts", "radar_desmontes.py"))
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)


def test_rangos_de_lectura():
    assert rd.lectura(-4.0)[0] == "confirma"
    assert rd.lectura(-2.0)[0] == "confirma"
    assert rd.lectura(-1.5)[0] == "cambio leve"
    assert rd.lectura(-1.0)[0] == "cambio leve"
    assert rd.lectura(-0.3)[0] == "sin cambio"
    assert rd.lectura(1.2)[0] == "sin cambio"


def _m(a, d, na=8, nd=8):
    return {"vh_antes": a, "vh_despues": d, "pasadas_antes": na, "pasadas_despues": nd}


def test_aplicar_agrega_senal_y_no_duplica():
    datos = {"parches": [
        {"id": "a", "senales": ["Grande: 120 ha.", "AlphaEarth: similitud 0,55."]},
        {"id": "b", "senales": []},
    ]}
    rd.aplicar(datos, {"a": _m(-13.0, -16.2)})
    rd.aplicar(datos, {"a": _m(-13.0, -16.2)})   # segunda corrida: no se repite
    a, b = datos["parches"]
    assert a["radar"] == {"vh_antes": -13.0, "vh_despues": -16.2, "delta_db": -3.2, "lectura": "confirma"}
    assert sum(s.startswith("Radar:") for s in a["senales"]) == 1
    assert "AlphaEarth: similitud 0,55." in a["senales"] and "-3,2" in a["senales"][-1]
    assert "radar" not in b and b["senales"] == []
    assert datos["radar"]["parches_evaluados"] == 1


def test_pocas_pasadas_no_se_evalua():
    datos = {"parches": [{"id": "a", "senales": []}]}
    rd.aplicar(datos, {"a": _m(-13.0, -17.0, na=2, nd=9)})
    assert "radar" not in datos["parches"][0]
    assert datos["radar"]["parches_evaluados"] == 0


def test_sin_cambio_cuando_el_monte_sigue_en_pie():
    datos = {"parches": [{"id": "a", "senales": []}]}
    rd.aplicar(datos, {"a": _m(-12.8, -13.1)})
    assert datos["parches"][0]["radar"]["lectura"] == "sin cambio"
