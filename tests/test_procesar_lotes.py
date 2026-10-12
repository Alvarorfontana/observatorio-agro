"""Procesamiento semanal: se prueba la cadena completa con una escena Sentinel-2 sintética
y el segmentador de prueba (sin red ni geoai). En GitHub Actions corre el modelo real."""
import json, os, sys, types
import pytest

np = pytest.importorskip("numpy")
rasterio = pytest.importorskip("rasterio")
pytest.importorskip("shapely")
pytest.importorskip("pyproj")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
import procesar_lotes as pl  # noqa: E402

LOT = {"id": "lote-test", "name": "no se imprime", "vertices": [[-28.512, -59.061], [-28.508, -59.032], [-28.531, -59.028], [-28.536, -59.052]]}


def _scene(tmp_path):
    """Escena UTM 21S (EPSG:32721): pasto (NDVI alto) con una laguna en el centro del lote."""
    from pyproj import Transformer
    from rasterio.transform import from_origin
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32721", always_xy=True)
    x0, y0 = tr.transform(-59.075, -28.495)
    x1, y1 = tr.transform(-59.015, -28.548)
    cx, cy = tr.transform(-59.045, -28.522)
    assets = {}
    for name, res in (("blue", 10), ("green", 10), ("red", 10), ("nir", 10), ("swir16", 20), ("swir22", 20)):
        w, h = int((x1 - x0) / res) + 1, int((y0 - y1) / res) + 1
        xs = x0 + (np.arange(w) + 0.5) * res; ys = y0 - (np.arange(h) + 0.5) * res
        X, Y = np.meshgrid(xs, ys)
        water = (X - cx) ** 2 + (Y - cy) ** 2 < 250 ** 2          # laguna de ~20 ha
        base = {"blue": 1400, "green": 1700, "red": 1500, "nir": 4200, "swir16": 3000, "swir22": 2200}[name]
        wat = {"blue": 1300, "green": 1500, "red": 1100, "nir": 900, "swir16": 1050, "swir22": 1020}[name]
        arr = np.where(water, wat, base).astype("uint16")           # +1000 de la línea base 04.00
        p = tmp_path / f"{name}.tif"
        with rasterio.open(p, "w", driver="GTiff", height=h, width=w, count=1, dtype="uint16", crs="EPSG:32721",
                           transform=from_origin(x0, y0, res, res)) as dst:
            dst.write(arr, 1)
        assets[name] = types.SimpleNamespace(href=str(p))
    return types.SimpleNamespace(id="S2X_TEST", assets=assets,
                                 properties={"datetime": "2026-10-08T14:00:00Z", "eo:cloud_cover": 3.2, "s2:processing_baseline": "05.11"})


def test_cadena_completa_detecta_agua_y_guarda_historial(tmp_path, monkeypatch):
    monkeypatch.setenv("DOTS_SEGMENTER", "fake")
    item = _scene(tmp_path)
    monkeypatch.setattr(pl, "find_scene", lambda bbox, today=None: item)
    data = tmp_path / "datos"; data.mkdir()
    (data / "lotes.json").write_text(json.dumps({"lotes": [LOT]}))
    pl.main(str(data))
    res = json.loads((data / "resultados" / "lote-test.json").read_text())
    assert res["status"] == "recibido" and res["scene"]["date"] == "2026-10-08"
    assert 12 < res["water_ha"] < 28 and res["water_bodies"] == 1        # la laguna, recortada al lote
    assert 0.65 < res["ndvi_mean"] < 0.75     # con el offset corregido; sin corregir daría ~0,47
    assert len(res["history"]) == 1 and res["water_geojson"]["features"]
    # segunda corrida con la misma escena: no duplica el historial
    pl.main(str(data))
    res2 = json.loads((data / "resultados" / "lote-test.json").read_text())
    assert len(res2["history"]) == 1
    idx = json.loads((data / "resultados" / "index.json").read_text())
    assert idx["lotes"]["lote-test"]["status"] == "recibido"


def test_sin_escena_conserva_el_ultimo_resultado(tmp_path, monkeypatch):
    data = tmp_path / "datos"; (data / "resultados").mkdir(parents=True)
    (data / "lotes.json").write_text(json.dumps({"lotes": [LOT]}))
    prev = {"status": "recibido", "water_ha": 5.0, "water_bodies": 2, "scene": {"date": "2026-09-30"}, "history": [{"scene_date": "2026-09-30", "water_ha": 5.0}]}
    (data / "resultados" / "lote-test.json").write_text(json.dumps(prev))
    monkeypatch.setattr(pl, "find_scene", lambda bbox, today=None: None)
    pl.main(str(data))
    res = json.loads((data / "resultados" / "lote-test.json").read_text())
    assert res["status"] == "sin dato" and res["stale"] is True and res["water_ha"] == 5.0 and len(res["history"]) == 1


def test_no_imprime_datos_del_lote(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pl, "find_scene", lambda bbox, today=None: None)
    data = tmp_path / "datos"; data.mkdir()
    (data / "lotes.json").write_text(json.dumps({"lotes": [LOT]}))
    pl.main(str(data))
    out = capsys.readouterr().out
    assert "no se imprime" not in out and "-28.5" not in out and "lote-test" not in out
