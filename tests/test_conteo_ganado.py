"""Conteo de ganado: partes que no necesitan descargar el modelo."""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("conteo_ganado", os.path.join(ROOT, "scripts", "conteo_ganado.py"))
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)


def test_clases_por_especie():
    assert cg.clases_de("vaca") == [21]
    assert cg.clases_de("Todas") == [19, 20, 21]
    with pytest.raises(SystemExit):
        cg.clases_de("cerdo")


def test_enlace_de_drive_pasa_a_descarga_directa():
    u = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/view?usp=sharing"
    assert cg.url_directa(u) == "https://drive.google.com/uc?export=download&id=1AbCdEfGhIjKlMnOpQrStUvWxYz012345"
    assert cg.url_directa("https://ejemplo.com/a.jpg") == "https://ejemplo.com/a.jpg"


def test_es_video():
    assert cg.es_video("x.MP4") and cg.es_video("x", "video/quicktime") and not cg.es_video("x.jpg", "image/jpeg")


def test_resumen_video():
    r = cg.resumen_video([3, 5, 4, 8], unicos=11)
    assert r == {"cuadros": 4, "maximo_en_un_cuadro": 8, "mediana_por_cuadro": 4.5, "distintos_estimados": 11}
    # el seguimiento nunca puede dar menos que lo visto en un solo cuadro
    assert cg.resumen_video([9, 2], unicos=4)["distintos_estimados"] == 9
    assert cg.resumen_video([], 0)["cuadros"] == 0


def test_rangos_de_confianza():
    assert cg.lectura_confianza(0.8)[0] == "alta"
    assert cg.lectura_confianza(0.55)[0] == "media"
    assert cg.lectura_confianza(0.2)[0] == "baja"


def test_foto_con_detector_simulado(tmp_path):
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    sv = pytest.importorskip("supervision")
    img = tmp_path / "campo.jpg"
    cv2.imwrite(str(img), np.full((300, 400, 3), 90, np.uint8))
    det = sv.Detections(xyxy=np.array([[10, 10, 60, 50], [100, 100, 150, 140]], float),
                        confidence=np.array([0.8, 0.6]), class_id=np.array([21, 21]))
    r = cg.contar_foto(str(img), lambda _: det, str(tmp_path / "salida.jpg"))
    assert r["total"] == 2 and r["por_especie"] == {"vaca": 2} and r["confianza_media"] == 0.7
    assert (tmp_path / "salida.jpg").exists()
    texto = cg.texto_resultado({**r, "generado": "2026-11-11T12:00:00", "origen": "x", "mosaico": True, "umbral": 0.4})
    assert "Animales detectados en la foto: 2 (vaca 2)" in texto and "0,70 (alta)" in texto
