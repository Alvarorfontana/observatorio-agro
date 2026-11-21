import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import evacuados as ev  # noqa: E402

PAGINA = """<html><body><h1>Monitoreo de Amenazas Naturales - 16 de noviembre del 2026</h1>
<p>No oficial</p><h3>Clima severo</h3>
<h4>Argentina (Actualización)</h4>
<p>El 16 de noviembre del 2026, medios de comunicación que citaron a la Agencia Federal de Emergencias (AFE)
informaron que 4.547 personas fueron evacuadas y autoevacuadas en 26 localidades de las provincias de Chaco,
Corrientes, Santa Fe y Entre Ríos debido a la crecida del río Paraná. Chaco concentra el mayor número de personas
afectadas, con 2.242, seguido de Corrientes, con 2.005.</p>
<h4>Guatemala</h4><p>Lluvias dejaron 30 personas evacuadas en Escuintla.</p>
<h4>Paraguay (Actualización)</h4><p>La Secretaría de Emergencia Nacional informó 120 familias desplazadas en Alberdi.</p>
</body></html>"""


class R:
    status_code = 200
    text = PAGINA


def test_lee_partes_de_la_cuenca_y_descarta_otros_paises():
    url, txt, err = ev.leer_dia(date(2026, 11, 16), get=lambda u: R())
    assert err is None and url.endswith("monitoreo-amenazas-naturales-16-noviembre-2026")
    partes = ev.partes_del_dia(date(2026, 11, 16), txt, url)
    paises = {p["pais"] for p in partes}
    assert paises == {"Argentina", "Paraguay"}
    arg = next(p for p in partes if p["pais"] == "Argentina")
    assert {"cantidad": 4547, "unidad": "personas"} in arg["cifras"]
    assert arg["organismo"] == "Agencia Federal de Emergencias"
    py = next(p for p in partes if p["pais"] == "Paraguay")
    assert py["cifras"] == [{"cantidad": 120, "unidad": "familias"}]
