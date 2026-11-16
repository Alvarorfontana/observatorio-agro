"""Anegamientos: cruce con el INA y ruta /api/fuentes/anegamientos."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import anegamientos_api as an

AVISOS = {"items": [
    {"id": "parana-goya", "place": "Goya", "river": "Paraná", "to": "Alerta", "height": 5.3, "date": "2026-10-18"},
    {"id": "parana-goya", "place": "Goya", "river": "Paraná", "to": "Evacuación", "height": 5.76, "date": "2026-10-29"},
    {"id": "uruguay-libres", "place": "Paso de los Libres", "river": "Uruguay", "to": "Alerta", "height": 7.5, "date": "2026-11-10"}]}


def _z(nombre, hoy, hab, nueva):
    return {"zona": nombre, "estado": "ok", "resumen": {"agua_hoy_ha": hoy, "agua_habitual_ha": hab, "agua_nueva_ha": nueva}}


def test_cruce_con_ina():
    data = an.armar({"zonas": [_z("Goya", 3132, 1008, 728), _z("Paso de los Libres", 400, 2848, 9),
                               _z("Mercedes", 2, 2, 0), {"zona": "Esquina", "estado": "cobertura insuficiente"}]}, AVISOS)
    g, p, m, e = data["zonas"]
    assert g["coincide"] is True and g["ina"]["to"] == "Evacuación" and g["ina"]["height"] == 5.76
    assert p["coincide"] is False and "menos agua" in p["contraste"]
    assert m["coincide"] is None and m["ina"] is None
    assert e["coincide"] is None
    # río en atención (no alto) pero el radar ve menos de la mitad del agua habitual: tampoco coincide
    aviso = {"items": [{"id": "uruguay-libres", "river": "Uruguay", "to": "Atención", "height": 6.99, "date": "2026-11-16"}]}
    assert an.armar({"zonas": [_z("Paso de los Libres", 400, 2848, 9)]}, aviso)["zonas"][0]["coincide"] is False


def test_ruta(monkeypatch):
    import datastore
    from api.index import app
    datos = {"anegamientos.json": {"zonas": [_z("Goya", 3132, 1008, 728)]}, "avisos.json": AVISOS,
             "anegamientos.geojson": {"type": "FeatureCollection", "features": []}}
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: datos.get(name))
    j = app.test_client().get("/api/fuentes/anegamientos").json
    assert j["status"] == "recibido" and j["data"]["zonas"][0]["coincide"] is True
    monkeypatch.setattr(datastore, "load", lambda name, *a, **k: None)
    assert app.test_client().get("/api/fuentes/anegamientos").json["status"] == "sin dato"
