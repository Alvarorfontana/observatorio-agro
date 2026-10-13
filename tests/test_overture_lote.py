"""Entorno del lote con Overture: cálculo con geometrías sintéticas y caché por versión (sin red)."""
import os, sys
import pytest

pytest.importorskip("shapely")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
import overture_lote as ov  # noqa: E402
import procesar_lotes as pl  # noqa: E402
from shapely.geometry import LineString, Polygon, box  # noqa: E402

LOT = box(-59.05, -28.53, -59.03, -28.51)          # ~2 km x 2,2 km
DEG_M = 1 / 111320


def test_summarize_caminos_construcciones_y_departamento():
    ruta = LineString([(-59.10, -28.50), (-59.00, -28.50)])             # al norte, ~1,1 km del lote
    camino = LineString([(-59.04, -28.54), (-59.04, -28.50)])           # cruza el lote de sur a norte
    sendero = LineString([(-59.045, -28.52), (-59.035, -28.52)])        # footway: no cuenta
    casa = box(-59.041, -28.521, -59.0408, -28.5208)                     # dentro
    galpon = box(-59.06, -28.52, -59.0598, -28.5198)                     # afuera, a menos de 2 km
    depto = Polygon([(-60, -29), (-58, -29), (-58, -28), (-60, -28)])
    out = ov.summarize(LOT, [(ruta, "primary"), (camino, "unclassified"), (sendero, "footway")],
                       [casa, galpon], [(depto, "county", "Mercedes"), (depto, "region", "Corrientes")])
    km = out["caminos_km"]
    assert 2.1 < km["caminos_lote"] < 2.3 and km["rutas_lote"] == 0
    assert km["rutas_2km"] > 3 and km["caminos_2km"] > km["caminos_lote"]
    assert out["camino_mas_cercano_m"] == 0 and 1000 < out["ruta_mas_cercana_m"] < 1200
    assert out["construcciones_lote"] == 1 and out["construcciones_2km"] == 2 and out["techo_m2_lote"] > 0
    assert out["departamento"] == "Mercedes" and out["provincia"] == "Corrientes"


def test_entorno_se_reutiliza_si_no_cambia_la_version(monkeypatch):
    calls = []
    class FakeReader:
        release = "2026-09-17.0"
    monkeypatch.setattr(ov, "latest_release", lambda: "2026-09-17.0")
    monkeypatch.setattr(ov, "Reader", lambda rel: FakeReader())
    monkeypatch.setattr(ov, "lot_context", lambda geom, r: calls.append(1) or {"release": r.release, "construcciones_lote": 3})
    lot = {"vertices": [[-28.51, -59.05], [-28.51, -59.03], [-28.53, -59.03]]}
    state = {}
    assert pl.entorno(lot, None, state)["construcciones_lote"] == 3 and len(calls) == 1
    prev = {"entorno": {"release": "2026-09-17.0", "construcciones_lote": 3}}
    assert pl.entorno(lot, prev, state) == prev["entorno"] and len(calls) == 1
    assert pl.entorno(lot, {"entorno": {"release": "viejo"}}, state)["release"] == "2026-09-17.0" and len(calls) == 2


def test_entorno_falla_sin_romper(monkeypatch):
    monkeypatch.setattr(ov, "latest_release", lambda: (_ for _ in ()).throw(RuntimeError("sin red")))
    state = {}
    prev = {"entorno": {"release": "x", "construcciones_lote": 1}}
    assert pl.entorno({"vertices": [[0, 0], [0, 1], [1, 1]]}, prev, state) == prev["entorno"]
    assert state["errors"] == 1 and state["last_error"] == "RuntimeError"


def test_reader_duckdb_con_geoparquet_local(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    from shapely import wkb as W
    db = duckdb.connect()
    def write(theme, kind, rows, extra):
        d = tmp_path / f"theme={theme}" / f"type={kind}"; d.mkdir(parents=True)
        db.execute(f"CREATE OR REPLACE TABLE t (geometry BLOB, bbox STRUCT(xmin DOUBLE, xmax DOUBLE, ymin DOUBLE, ymax DOUBLE), {extra})")
        for g, vals in rows:
            x0, y0, x1, y1 = g.bounds
            db.execute(f"INSERT INTO t VALUES (?, {{'xmin': ?, 'xmax': ?, 'ymin': ?, 'ymax': ?}}, {', '.join('?' * len(vals))})",
                       [W.dumps(g), x0, x1, y0, y1, *vals])
        db.execute(f"COPY t TO '{d}/part-0.parquet' (FORMAT parquet)")
    write("transportation", "segment", [(LineString([(-59.04, -28.54), (-59.04, -28.50)]), ["road", "track"]),
                                        (LineString([(-58.0, -27.0), (-57.9, -27.0)]), ["road", "primary"])], "subtype VARCHAR, class VARCHAR")
    write("buildings", "building", [(box(-59.041, -28.521, -59.0408, -28.5208), [1])], "level INTEGER")
    write("divisions", "division_area", [(box(-60, -29, -58, -28), ["county", {"primary": "Mercedes"}])],
          "subtype VARCHAR, names STRUCT(\"primary\" VARCHAR)")
    out = ov.lot_context(LOT, ov.Reader("local", base=str(tmp_path)))
    assert out["caminos_km"]["caminos_lote"] > 2 and out["ruta_mas_cercana_m"] is None
    assert out["construcciones_lote"] == 1 and out["departamento"] == "Mercedes" and out["release"] == "local"
