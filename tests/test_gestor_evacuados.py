import importlib.util
import os
from datetime import datetime, timedelta, timezone

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("gestor_evacuados", os.path.join(RAIZ, "scripts", "gestor_evacuados.py"))
ge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ge)


def test_cifras_espanol():
    out = ge.cifras("La provincia cuenta con 468 evacuados y 1.537 autoevacuados")
    assert {"cifra": 468, "que": "evacuados"} in out
    assert {"cifra": 1537, "que": "autoevacuados"} in out


def test_cifras_familias_y_personas():
    out = ge.cifras("Suman 2.239 personas evacuadas, de 629 hogares; hay 63 familias en Paraná")
    assert {"cifra": 2239, "que": "evacuados"} in out
    assert {"cifra": 629, "que": "hogares"} in out
    assert {"cifra": 63, "que": "familias"} in out


def test_cifras_portugues():
    out = ge.cifras("Uruguaiana tem 176 desalojados e 41 desabrigados")
    assert out == [{"cifra": 176, "que": "desalojados"}, {"cifra": 41, "que": "desabrigados"}]


def test_sin_cifras():
    assert ge.cifras("Alerta por la crecida del Paraná en Santa Fe") == []


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Corrientes tiene 1.967 evacuados por la crecida - El Litoral</title>
<link>https://ejemplo.com/a</link><pubDate>{reciente}</pubDate><source url="x">El Litoral</source>
<description>Son 444 los evacuados</description></item>
<item><title>Nota vieja con 50 evacuados - Diario</title><link>https://ejemplo.com/b</link>
<pubDate>Mon, 02 Jan 2023 10:00:00 GMT</pubDate><source url="x">Diario</source><description></description></item>
<item><title>El río sigue alto - Diario</title><link>https://ejemplo.com/c</link>
<pubDate>{reciente}</pubDate><source url="x">Diario</source><description></description></item>
</channel></rss>"""


def test_juntar_filtra_viejas_sin_cifras_y_repetidas():
    ahora = datetime.now(timezone.utc)
    reciente = ahora.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = RSS.format(reciente=reciente)
    cfg = {
        "idiomas": {"es": {"palabras": ["evacuados"], "google": {"hl": "es-419", "gl": "AR", "ceid": "AR:es-419"}}},
        "paises": {"Argentina": {"idioma": "es", "nacional": [],
                                 "provincias": {"Corrientes": {"rio": "Paraná", "municipios": ["Goya"]}}}},
    }
    partes, sin_partes, oficiales_sin, errores = ge.juntar(cfg, ahora - timedelta(days=7), traer=lambda url: xml)
    assert errores == []
    assert len(partes) == 1  # la vieja y la que no tiene cifras quedan afuera; la repetida en la provincia también
    p = partes[0]
    assert p["lugar"] == "Goya" and p["nivel"] == "municipio" and p["medio"] == "El Litoral"
    assert p["titulo"] == "Corrientes tiene 1.967 evacuados por la crecida"
    assert {"cifra": 1967, "que": "evacuados"} in p["cifras"] and p["estado"] == "a verificar"
    assert "Corrientes (Argentina)" in sin_partes


def test_informe_formal_sin_emojis():
    ahora = datetime.now(timezone.utc)
    partes = [{"fecha": ahora.strftime("%Y-%m-%d"), "pais": "Uruguay", "provincia": "Salto", "lugar": "Salto",
               "nivel": "provincia", "rio": "Uruguay", "titulo": "Hay 100 desplazados", "medio": "Radio",
               "enlace": "https://ejemplo.com", "cifras": [{"cifra": 100, "que": "desplazados"}], "estado": "a verificar"}]
    txt = ge.informe(partes, ["Paysandú (Uruguay)"], [], ahora - timedelta(days=7), ahora)
    assert "100 desplazados" in txt and "Sin partes nuevos" in txt and "a verificar" in txt
    assert all(ord(c) < 0x2000 for c in txt)


def test_lista_de_lugares_valida():
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(RAIZ, "gestores", "evacuados.yml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    lus = ge.lugares(cfg)
    assert {l["pais"] for l in lus} == {"Argentina", "Uruguay", "Paraguay", "Brasil"}
    assert all(l["idioma"] in cfg["idiomas"] for l in lus)
    niveles = [l["nivel"] for l in lus]
    assert niveles.index("provincia") > niveles.index("municipio")


GDELT = """{"articles":[{"url":"https://diario.com.py/x","title":"Pilar: 320 familias evacuadas por la crecida",
"seendate":"%s","domain":"diario.com.py","sourcecountry":"Paraguay"},
{"url":"https://diario.com.py/y","title":"Clima en Paraguay","seendate":"%s","domain":"diario.com.py"}]}"""


def test_gdelt_asigna_lugar_por_titular_y_oficiales():
    ahora = datetime.now(timezone.utc)
    sd = ahora.strftime("%Y%m%dT%H%M%SZ")
    cfg = {
        "idiomas": {"es-PY": {"palabras": ["evacuados"], "google": {"hl": "es-419", "gl": "PY", "ceid": "PY:es-419"}}},
        "paises": {"Paraguay": {"idioma": "es-PY", "nacional": [],
                                "provincias": {"Ñeembucú": {"rio": "Paraguay", "municipios": ["Pilar"]}}}},
        "oficiales": {"Paraguay": [{"organismo": "SEN", "jurisdiccion": "Nación", "dominio": "sen.gov.py"}]},
        "gdelt": {"Paraguay": {"pais_fuente": "paraguay", "palabras": ["evacuados"]}},
    }
    vacio = "<rss><channel></channel></rss>"
    traer = lambda url: (GDELT % (sd, sd)) if "gdeltproject" in url else vacio
    partes, sin_partes, oficiales_sin, errores = ge.juntar(cfg, ahora - timedelta(days=7), traer=traer)
    assert errores == []
    assert len(partes) == 1 and partes[0]["lugar"] == "Pilar" and partes[0]["motor"] == "GDELT"
    assert {"cifra": 320, "que": "familias"} in partes[0]["cifras"]
    assert oficiales_sin == ["SEN (sen.gov.py)"]
    assert any("site:sen.gov.py" in ge.unquote(b["url"]) for b in ge.busquedas(cfg)[0])


def test_gdelt_texto_plano_no_rompe():
    assert ge.leer_gdelt("Your query was too short") == []
