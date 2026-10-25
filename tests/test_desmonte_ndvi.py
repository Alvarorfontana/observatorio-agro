"""Desmontes por resta de NDVI: partes que no necesitan red ni Earth Engine."""
import importlib.util
import json
import os
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("desmonte_ndvi", os.path.join(ROOT, "scripts", "desmonte_ndvi.py"))
dn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dn)


def test_verano_usa_el_ultimo_terminado():
    antes, despues = dn.ventanas("verano", hoy=date(2026, 10, 25))
    assert antes == ("2024-12-01", "2025-04-01") and despues == ("2025-12-01", "2026-04-01")
    # en febrero el verano en curso todavía no terminó
    antes, despues = dn.ventanas("verano", hoy=date(2026, 2, 10))
    assert despues == ("2024-12-01", "2025-04-01")


def test_reciente_compara_los_mismos_dias_del_anio_anterior():
    antes, despues = dn.ventanas("reciente", hoy=date(2026, 10, 25))
    assert despues[1] == "2026-10-20" and antes[1] == "2025-10-20"
    assert (date.fromisoformat(despues[1]) - date.fromisoformat(despues[0])).days == 120


def test_rotulo_ventana():
    assert dn.rotulo_ventana(("2025-12-01", "2026-04-01")) == "dic 2025 – mar 2026"


def test_grilla_sin_repetir_y_cubre_las_cajas():
    celdas = dn.grilla([(-60.2, -28.9, -59.1, -27.6), (-59.6, -28.4, -59.2, -28.1)], paso=0.5)
    assert len(celdas) == len(set(celdas)) == 3 * 3
    assert min(c[0] for c in celdas) <= -60.2 and max(c[2] for c in celdas) >= -59.1


def test_nombres_sin_acentos():
    assert dn.norm("Entre Ríos") == dn.norm("entre rios") == "entre rios"
    assert dn.norm("Tucumán ") == "tucuman"


@pytest.mark.parametrize("valor,esperado", [("I", "rojo"), ("Categoría II", "amarillo"), ("Amarilla", "amarillo"),
                                            ("3", "verde"), ("Rojo", "rojo"), ("", None)])
def test_categoria_otbn(valor, esperado):
    assert dn.categoria_otbn(valor) == esperado


def test_bosque_en_zona_roja_es_grave():
    nivel, tipo, senales = dn.evaluar({"area_ha": 320, "bosque_2020": 0.9, "otbn": "rojo", "frac_estricto": 0.7})
    assert nivel == "alto" and tipo == "desmonte probable"
    assert any("zona roja" in s.lower() for s in senales) and any("EUDR" in s for s in senales)


def test_parche_chico_sin_bosque_es_bajo():
    nivel, _, _ = dn.evaluar({"area_ha": 15, "bosque_2020": 0.05, "frac_medio": 0.6})
    assert nivel == "bajo"


def test_incendio_no_queda_como_alto():
    nivel, tipo, senales = dn.evaluar({"area_ha": 900, "bosque_2020": 0.8, "otbn": "rojo", "fuego": 0.6})
    assert tipo == "posible incendio" and nivel == "medio"
    assert "quemado" in senales[0]


def test_armar_parche_da_rango_de_superficie():
    props = {"lat": -26.12345678, "lon": -61.5, "area_ha": 311.0, "frac_medio": 0.8, "frac_estricto": 0.5627,
             "ndvi_antes": 0.81, "ndvi_despues": 0.22, "dndvi": -0.59, "bosque_2020": 0.95}
    geom = {"type": "Polygon", "coordinates": [[[-61.5, -26.1], [-61.49, -26.1], [-61.49, -26.11], [-61.5, -26.1]]]}
    p = dn.armar_parche(props, geom, "verano", lugar={"provincia": "Chaco", "departamento": "Almirante Brown"})
    assert p["area_ha"] == {"amplio": 311.0, "medio": 248.8, "estricto": 175.0}
    assert p["lat"] == -26.12346 and p["provincia"] == "Chaco" and p["nivel"] in ("alto", "medio")
    json.dumps(p)


def test_unir_bordes_junta_partes_que_se_tocan():
    pytest.importorskip("shapely")

    def f(w, e, area, b):
        return {"geometry": {"type": "Polygon", "coordinates": [[[w, -26.0], [e, -26.0], [e, -25.9], [w, -25.9], [w, -26.0]]]},
                "properties": {"area_ha": area, "bosque_2020": b, "lat": -25.95, "lon": (w + e) / 2}}
    juntos = dn.unir_bordes([f(-61.1, -61.0, 100, 1.0), f(-61.0, -60.9, 300, 0.0), f(-60.0, -59.9, 50, 0.5)])
    assert len(juntos) == 2
    grande = max(juntos, key=lambda x: x["properties"]["area_ha"])
    assert grande["properties"]["area_ha"] == 400 and grande["properties"]["bosque_2020"] == pytest.approx(0.25)


def test_resumen_por_provincia_y_nivel():
    ps = [{"provincia": "Salta", "area_ha": {"amplio": 100, "medio": 80, "estricto": 50}, "nivel": "alto"},
          {"provincia": "Chaco", "area_ha": {"amplio": 300, "medio": 200, "estricto": 100}, "nivel": "bajo"},
          {"provincia": None, "area_ha": {"amplio": 10, "medio": 5, "estricto": 1}, "nivel": "medio"}]
    r = dn.resumen(ps)
    assert list(r["provincias"])[0] == "Chaco" and r["niveles"] == {"alto": 1, "medio": 1, "bajo": 1}
    assert r["ha_total"]["amplio"] == 410
