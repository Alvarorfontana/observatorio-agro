"""Manchas de agua: speckle, fondo con recorte sigma, catálogo de manchas y Hampel, con escenas sintéticas."""
import os, sys
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
import manchas_agua as ma  # noqa: E402

RNG = np.random.default_rng(7)


def _escena(db_medio, forma=(120, 120), ruido_db=1.0):
    return db_medio + RNG.normal(0, ruido_db, forma)


def test_lee_reduce_speckle_y_respeta_nan():
    base = 10 ** (-10 / 10)
    speckle = base * RNG.gamma(4.4, 1 / 4.4, (80, 80))
    speckle[0, 0] = np.nan
    limpio = ma.filtro_lee(speckle)
    assert np.isnan(limpio[0, 0])
    assert np.nanstd(limpio) < 0.6 * np.nanstd(speckle)
    assert abs(np.nanmean(limpio) - base) / base < 0.05


def test_sigma_recortado_descarta_pasada_rara():
    pila = np.stack([_escena(-10, (20, 20), 0.5) for _ in range(9)])
    pila[3] = -25.0  # una inundación vieja en una sola fecha
    med, sd, n = ma.sigma_recortado(pila)
    assert np.allclose(np.nanmedian(med), -10, atol=0.3)
    assert np.nanmedian(sd) < 1.0
    assert np.all(n <= 8)


def test_otsu_encuentra_umbral_con_dos_clases_y_none_sin_agua():
    mezcla = np.concatenate([RNG.normal(-22, 1.5, 4000), RNG.normal(-9, 1.5, 6000)])
    t = ma.umbral_otsu(mezcla)
    assert t is not None and -19 < t < -12
    assert ma.umbral_otsu(RNG.normal(-9, 1.5, 6000)) is None


def test_detecta_mancha_nueva_y_no_el_agua_habitual():
    fondo = np.full((120, 120), -9.0)
    fondo[:, :15] = -23.0                     # río de siempre
    sd = np.full_like(fondo, 0.8)
    hoy = _escena(-9, ruido_db=0.4)
    hoy[:, :15] = -23.0
    hoy[40:70, 50:90] = -21.0                 # anegamiento nuevo: 30 × 40 px
    hoy[5, 100] = -22.0                       # píxel suelto: debe caer
    manchas, etiquetas, resumen = ma.detectar_manchas(
        hoy, fondo, sd, area_pixel_m2=400, a_lonlat=lambda f, c: (-58.8 + c * 0.0002, -27.4 - f * 0.0002))
    assert len(manchas) == 1
    m = manchas[0]
    assert 40 <= m["superficie_ha"] <= 50     # 1200 px × 400 m² = 48 ha
    assert m["intensidad"] == "fuerte"
    assert 50 <= m["fila_col"][0] <= 60 and 65 <= m["fila_col"][1] <= 75
    assert len(m["centroide"]) == 2
    assert resumen["agua_habitual_ha"] > 0 and resumen["agua_nueva_ha"] == m["superficie_ha"]
    assert etiquetas[5, 100] == 0


def test_manchas_chicas_se_descartan_por_superficie():
    fondo = np.full((60, 60), -9.0)
    hoy = fondo.copy()
    hoy[10:14, 10:14] = -22.0                 # 16 px × 400 m² = 0,64 ha < 1 ha
    manchas, _, _ = ma.detectar_manchas(hoy, fondo, np.full_like(fondo, 0.8), 400)
    assert manchas == []


def test_intensidad_rangos():
    assert ma.intensidad(-6) == "fuerte"
    assert ma.intensidad(-4.5) == "moderada"
    assert ma.intensidad(-3.2) == "leve"


def test_hampel_marca_fecha_rara_sin_tocar_las_demas():
    serie = [0.10, 0.11, 0.10, 0.12, 0.45, 0.11, 0.10, float("nan"), 0.11]
    raro = ma.hampel(serie)
    assert raro.tolist().count(True) == 1 and raro[4]


def test_cadena_completa_con_pasadas_sinteticas(tmp_path, monkeypatch):
    """Zona completa sin red: 12 pasadas de fondo + una con anegamiento, salida JSON y GeoJSON."""
    pytest.importorskip("rasterio")
    pytest.importorskip("pyproj")
    pytest.importorskip("shapely")
    import json
    import anegamientos as an

    fechas = [f"2026-{m:02d}-{d:02d}T09:30:00Z" for m in range(1, 12) for d in (5,)] + ["2026-11-10T09:30:00Z"]
    escenas = [{"id": f"s{i}", "properties": {"datetime": f, "sat:orbit_state": "descending",
                                               "sat:relative_orbit": 10}, "assets": {"vv": {}}}
               for i, f in enumerate(fechas)]
    escenas.append({"id": "otra", "properties": {"datetime": "2026-11-12T09:30:00Z", "sat:orbit_state": "ascending",
                                                  "sat:relative_orbit": 99}, "assets": {"vv": {}}})
    monkeypatch.setattr(an, "buscar", lambda bbox, dias: escenas)
    rng = np.random.default_rng(1)

    def leer(escena, transform, ancho, alto):
        db = np.full((alto, ancho), -9.0) + rng.normal(0, 0.5, (alto, ancho))
        db[:, :60] = -23.0                                   # río
        if escena["id"] == "s3":
            db[200:260, 300:400] = -22.0                     # crecida vieja: el recorte sigma la saca
        if escena["id"] == "s11":
            db[400:500, 500:650] = -21.0                     # anegamiento actual: 100 × 150 px = 600 ha
        return 10 ** (db / 10)

    monkeypatch.setattr(an, "leer_vv", leer)
    monkeypatch.setattr(an, "SALIDA", tmp_path)
    monkeypatch.setenv("ANEG_ZONAS", "Goya")
    an.main()
    datos = json.loads((tmp_path / "anegamientos.json").read_text(encoding="utf-8"))
    z = datos["zonas"][0]
    assert z["estado"] == "ok" and z["orbita"] == "descending/10"
    assert len(z["manchas"]) == 1 and 550 <= z["manchas"][0]["superficie_ha"] <= 620
    lon, lat = z["manchas"][0]["centroide"]
    assert -59.4 < lon < -59.1 and -29.3 < lat < -29.0
    assert z["serie"][-1]["fecha"] == "2026-11-10"
    geo = json.loads((tmp_path / "anegamientos.geojson").read_text(encoding="utf-8"))
    assert len(geo["features"]) == 1 and geo["features"][0]["properties"]["zona"] == "Goya"


def test_otsu_fuera_de_rango_vuelve_a_none():
    # dos modos, pero el corte cae en −13 dB (suelo mojado contra suelo seco): no se acepta como agua
    mezcla = np.concatenate([RNG.normal(-15, 0.8, 4000), RNG.normal(-10, 0.8, 6000)])
    assert ma.umbral_otsu(mezcla) is None


def _escenas_dia(fecha, tramos=1, orbita=10):
    return [{"id": f"{fecha}-{t}", "tramo": t, "properties": {"datetime": f"{fecha}T09:30:0{t}Z",
             "sat:orbit_state": "descending", "sat:relative_orbit": orbita}, "assets": {"vv": {}}}
            for t in range(tramos)]


def test_une_tramos_del_mismo_dia_y_exige_cobertura(tmp_path, monkeypatch):
    """El recuadro cae en el borde entre dos tramos: sin unirlos, cada uno cubre la mitad."""
    pytest.importorskip("rasterio")
    pytest.importorskip("pyproj")
    pytest.importorskip("shapely")
    import json
    import anegamientos as an
    fechas = [f"2026-{m:02d}-05" for m in range(1, 11)] + ["2026-11-10"]
    escenas = [e for f in fechas for e in _escenas_dia(f, tramos=2)]
    monkeypatch.setattr(an, "buscar", lambda bbox, dias: escenas)

    def leer(escena, transform, ancho, alto):
        db = np.full((alto, ancho), -9.0)
        db[:, :60] = -23.0
        mitad = alto // 2
        if escena["tramo"] == 0:
            db[mitad:, :] = np.nan
        else:
            db[:mitad, :] = np.nan
        return 10 ** (db / 10)

    monkeypatch.setattr(an, "leer_vv", leer)
    monkeypatch.setattr(an, "SALIDA", tmp_path)
    monkeypatch.setenv("ANEG_ZONAS", "Corrientes (capital)")
    an.main()
    z = json.loads((tmp_path / "anegamientos.json").read_text(encoding="utf-8"))["zonas"][0]
    assert z["estado"] == "ok" and z["cobertura"] > 0.99
    assert z["resumen"]["agua_habitual_ha"] > 0

    # si el último día solo trae un tramo (media zona), no se informa
    escenas[:] = [e for e in escenas if not (e["properties"]["datetime"].startswith("2026-11-10") and e["tramo"] == 1)]
    monkeypatch.setattr(an, "SALIDA", tmp_path)
    with pytest.raises(SystemExit):
        an.main()
    z = json.loads((tmp_path / "anegamientos.json").read_text(encoding="utf-8"))["zonas"][0]
    assert z["estado"] == "cobertura insuficiente"
