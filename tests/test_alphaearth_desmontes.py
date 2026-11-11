"""Segunda opinión de AlphaEarth sobre desmontes: partes que no necesitan red ni Earth Engine."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("alphaearth_desmontes", os.path.join(ROOT, "scripts", "alphaearth_desmontes.py"))
ae = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ae)


def test_rangos_de_lectura():
    assert ae.lectura(0.97)[0] == "sin cambio"
    assert ae.lectura(0.90)[0] == "sin cambio"
    assert ae.lectura(0.80)[0] == "cambio moderado"
    assert ae.lectura(0.40)[0] == "cambio fuerte"
    assert ae.lectura(-0.2)[0] == "cambio fuerte"


def test_elegir_anios_usa_el_ultimo_mapa_disponible():
    antes = {"desde": "2024-12-01", "hasta": "2025-04-01"}
    despues = {"desde": "2025-12-01", "hasta": "2026-04-01"}
    assert ae.elegir_anios(antes, despues, ultimo=2025) == (2024, 2025)
    assert ae.elegir_anios(antes, despues, ultimo=2026) == (2024, 2026)


def test_elegir_anios_sin_mapa_posterior():
    antes = {"desde": "2025-06-01", "hasta": "2025-10-01"}
    despues = {"desde": "2026-06-01", "hasta": "2026-10-01"}
    assert ae.elegir_anios(antes, despues, ultimo=2025) is None


def test_aplicar_agrega_senal_y_no_duplica():
    datos = {"parches": [
        {"id": "a", "senales": ["Grande: 120 ha."]},
        {"id": "b", "senales": []},
    ]}
    ae.aplicar(datos, {"a": 0.55}, (2024, 2025))
    ae.aplicar(datos, {"a": 0.55}, (2024, 2025))   # segunda corrida: no se repite
    a, b = datos["parches"]
    assert a["alphaearth"] == {"similitud": 0.55, "lectura": "cambio fuerte"}
    assert sum(s.startswith("AlphaEarth:") for s in a["senales"]) == 1
    assert "0,55" in a["senales"][-1] and "Grande: 120 ha." in a["senales"]
    assert "alphaearth" not in b and b["senales"] == []
    assert datos["alphaearth"]["anio_antes"] == 2024 and datos["alphaearth"]["parches_evaluados"] == 1
