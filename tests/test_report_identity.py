"""Contrato de identidad documental para los informes PDF DOTS.

No requiere datos externos: verifica que cada plantilla especializada utilice
la misma identidad y que no vuelva a definir la marca por separado.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("dots.typ", "cuenca.typ", "localidad.typ", "poblacion.typ", "enso.typ", "campo.typ", "eudr.typ")


def test_shared_identity_exists():
    source = (ROOT / "report" / "identity.typ").read_text(encoding="utf-8")
    assert "Sistema de Inteligencia Territorial, Ambiental y Climática" in source
    assert "Álvaro Fontana" in source
    assert "#let cover-id()" in source


def test_every_typst_report_imports_common_identity():
    for filename in TEMPLATES:
        source = (ROOT / "report" / filename).read_text(encoding="utf-8")
        assert '#import "identity.typ":' in source, filename
        assert "#cover-id()" in source, filename
        assert "author: name" in source, filename
        assert 'author: "DOTS / Campo"' not in source, filename


def test_general_pdf_has_institutional_footer():
    source = (ROOT / "informe_temas.py").read_text(encoding="utf-8")
    assert "Dirección: Álvaro Fontana" in source
    assert "onFirstPage=institutional_page" in source
    assert "onLaterPages=institutional_page" in source
