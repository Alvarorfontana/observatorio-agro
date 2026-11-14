"""Alerta temprana de estrés hídrico: rangos, falta de historia y cadena completa con escena sintética."""
import json, os, sys
import pytest

pytest.importorskip("numpy")
pytest.importorskip("rasterio")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import anomalia_lote as al  # noqa: E402
import procesar_lotes as pl  # noqa: E402
from test_procesar_lotes import LOT, _scene  # noqa: E402

BASE = [{"year": 2021 + i, "ndvi": v, "lswi": w} for i, (v, w) in enumerate([(0.70, 0.30), (0.72, 0.32), (0.68, 0.28), (0.71, 0.31), (0.69, 0.29)])]


def test_normal_moderada_fuerte():
    assert al.evaluate(0.70, 0.30, BASE)["nivel"] == "normal"
    assert al.evaluate(0.70, 0.27, BASE)["nivel"] == "moderada"
    r = al.evaluate(0.55, 0.10, BASE)
    assert r["nivel"] == "fuerte" and r["orientativo"] and len(r["rangos"]) == 3


def test_lswi_adelanta_al_ndvi():
    r = al.evaluate(0.70, 0.27, BASE)
    assert r["adelanto"] and "señal temprana" in r["texto"]


def test_sin_historia_suficiente():
    r = al.evaluate(0.7, 0.3, BASE[:2])
    assert r["status"] == "sin base" and r["years"] == 2


def test_cadena_completa_guarda_base_y_no_la_recalcula(tmp_path, monkeypatch):
    monkeypatch.setenv("DOTS_SEGMENTER", "fake")
    monkeypatch.setenv("DOTS_OVERTURE", "0")
    item = _scene(tmp_path)
    calls = []
    def find(bbox, today=None, lookback=45):
        calls.append(lookback); return item
    monkeypatch.setattr(pl, "find_scene", find)
    data = tmp_path / "datos"; data.mkdir()
    (data / "lotes.json").write_text(json.dumps({"lotes": [LOT]}))
    pl.main(str(data))
    res = json.loads((data / "resultados" / "lote-test.json").read_text())
    a = res["anomalia"]
    assert a["status"] == "recibido" and a["nivel"] == "normal" and a["years"] == al.BASE_YEARS
    assert a["lswi"] is not None and "S41" in res["bases"]
    first = len(calls)
    pl.main(str(data))                      # misma semana: la base sale del resultado guardado
    assert len(calls) == first + 1
