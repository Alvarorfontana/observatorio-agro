"""Pruebas del evaluador de máscaras; no representan validación de escenas reales."""
import pytest

np = pytest.importorskip("numpy")
from atlas_lab.evaluar_manchas_agua import calcular_metricas


def test_metricas_perfectas():
    mask = np.array([[1, 0], [1, 0]], dtype=bool)
    result = calcular_metricas(mask, mask, area_pixel_m2=100)
    assert result["confusion"] == {
        "true_positive": 2, "false_positive": 0,
        "false_negative": 0, "true_negative": 2,
    }
    assert result["metrics"]["precision"] == 1
    assert result["metrics"]["recall"] == 1
    assert result["metrics"]["f1"] == 1
    assert result["metrics"]["iou"] == 1
    assert result["metrics"]["absolute_area_error_m2"] == 0


def test_falsos_positivos_y_negativos():
    pred = np.array([[1, 1], [0, 0]], dtype=bool)
    ref = np.array([[1, 0], [1, 0]], dtype=bool)
    result = calcular_metricas(pred, ref)
    assert result["confusion"]["true_positive"] == 1
    assert result["confusion"]["false_positive"] == 1
    assert result["confusion"]["false_negative"] == 1
    assert result["confusion"]["true_negative"] == 1
    assert result["metrics"]["precision"] == 0.5
    assert result["metrics"]["recall"] == 0.5
    assert result["metrics"]["f1"] == 0.5
    assert result["metrics"]["iou"] == 1 / 3


def test_excluye_pixeles_sin_referencia():
    pred = np.array([[1, 1], [0, 0]], dtype=bool)
    ref = np.array([[1, 0], [1, 0]], dtype=bool)
    valid = np.array([[1, 0], [1, 0]], dtype=bool)
    result = calcular_metricas(pred, ref, valido=valid)
    assert result["coverage"]["valid_pixels"] == 2
    assert result["coverage"]["total_pixels"] == 4
    assert result["coverage"]["valid_fraction"] == 0.5
    assert result["confusion"]["false_positive"] == 0


def test_rechaza_formas_incompatibles():
    with pytest.raises(ValueError):
        calcular_metricas(np.zeros((2, 2)), np.zeros((3, 3)))
