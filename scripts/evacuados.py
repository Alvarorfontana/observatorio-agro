"""Gestor de evacuados: partes oficiales de evacuados y autoevacuados en la Cuenca del Plata.

No hay una API pública de evacuados. La fuente más ordenada y regular es el «Monitoreo de Amenazas Naturales»
diario de la Organización Panamericana de la Salud (OPS/PAHO), que resume los partes de los organismos oficiales
(Agencia Federal de Emergencias y Defensas Civiles de Argentina, SEN de Paraguay, SINAE de Uruguay, Defesa Civil
de Brasil). Este script lee los últimos días, se queda con los párrafos de los cuatro países que hablan de
evacuados, extrae las cifras y anota el organismo que las informó y el enlace.

DOTS no estima evacuados: si un día no hay parte, ese día queda sin dato.

Uso: python scripts/evacuados.py data/evacuados.json [días]
"""
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
URL = "https://www.paho.org/es/monitoreo-amenazas-naturales/monitoreo-amenazas-naturales-{d}-{mes}-{y}"
PAISES = ["Argentina", "Paraguay", "Uruguay", "Brasil"]
OTROS_PAISES = ["Bolivia", "Chile", "Perú", "Ecuador", "Colombia", "Venezuela", "México", "Guatemala", "Honduras",
                "Haití", "Cuba", "Panamá", "Costa Rica", "Nicaragua", "El Salvador", "República Dominicana",
                "Estados Unidos", "Canadá", "Jamaica", "Belice", "Guyana", "Surinam"]
ORGANISMOS = [
    "Agencia Federal de Emergencias", "Defensa Civil", "Protección Civil", "Defesa Civil", "SINAGIR",
    "Sistema Nacional de Emergencias", "SINAE", "Secretaría de Emergencia Nacional", "SEN",
    "Comité de Emergencia", "Comité Técnico de Emergencia", "Municipalidad de [A-ZÁÉÍÓÚ][\\wáéíóúñ ]+",
    "Gobierno de(?:l)? [A-ZÁÉÍÓÚ][\\wáéíóúñ ]+",
]
PALABRAS = re.compile(r"evacuad|autoevacuad|desplazad|desalojad|damnificad|desabrigad|desalojad", re.I)
CIFRA = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+|\d+)\s+(personas|familias|hogares|habitantes|pessoas|famílias)", re.I)


def texto(html_doc):
    html_doc = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html_doc)
    html_doc = re.sub(r"(?i)<br\s*/?>|</(p|h\d|li|div)>", "\n", html_doc)
    return html.unescape(re.sub(r"<[^>]+>", " ", html_doc))


def bloques_por_pais(txt):
    """Corta el texto en bloques que empiezan con el nombre de un país como encabezado («Argentina (Actualización)»)."""
    todos = PAISES + OTROS_PAISES
    pat = re.compile(r"^\s*(" + "|".join(map(re.escape, todos)) + r")\b[^\n]{0,40}$", re.M)
    marcas = [(m.start(), m.group(1)) for m in pat.finditer(txt)]
    out = []
    for i, (ini, pais) in enumerate(marcas):
        fin = marcas[i + 1][0] if i + 1 < len(marcas) else len(txt)
        if pais in PAISES:
            out.append((pais, txt[ini:fin]))
    return out


def oraciones(bloque):
    plano = " ".join(bloque.split())
    return [o.strip() for o in re.split(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚ0-9])", plano) if o.strip()]


def cifras(oracion):
    out = []
    for m in CIFRA.finditer(oracion):
        n = int(re.sub(r"[.\s]", "", m.group(1)))
        out.append({"cantidad": n, "unidad": m.group(2).lower().replace("pessoas", "personas").replace("famílias", "familias")})
    return out


def organismo(oracion):
    for o in ORGANISMOS:
        m = re.search(o, oracion)
        if m:
            return m.group(0).strip()
    return None


def leer_dia(dia, get=None):
    get = get or (lambda u: requests.get(u, timeout=40, headers={"User-Agent": "DOTS-observatorio/1.0"}))
    url = URL.format(d=dia.day, mes=MESES[dia.month - 1], y=dia.year)
    try:
        r = get(url)
    except Exception as exc:
        return url, None, f"no respondió ({type(exc).__name__})"
    if getattr(r, "status_code", 200) != 200:
        return url, None, f"HTTP {r.status_code}"
    return url, texto(r.text), None


def partes_del_dia(dia, txt, url):
    partes = []
    for pais, bloque in bloques_por_pais(txt):
        for o in oraciones(bloque):
            if not PALABRAS.search(o):
                continue
            c = cifras(o)
            partes.append({"fecha_informe": dia.isoformat(), "pais": pais, "texto": o[:700], "cifras": c,
                           "organismo": organismo(o), "fuente": "OPS · Monitoreo de Amenazas Naturales",
                           "url": url})
    return partes


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/evacuados.json"
    dias = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    hoy = datetime.now(timezone.utc).date()
    previo = {}
    if os.path.exists(out_path):
        try:
            previo = json.load(open(out_path))
        except ValueError:
            previo = {}
    partes = {(p["fecha_informe"], p["texto"]): p for p in previo.get("partes", [])}
    revisados, sin_parte = [], []
    for i in range(dias):
        dia = hoy - timedelta(days=i)
        url, txt, err = leer_dia(dia)
        if txt is None:
            sin_parte.append({"fecha": dia.isoformat(), "motivo": err})
            continue
        nuevos = partes_del_dia(dia, txt, url)
        revisados.append(dia.isoformat())
        for p in nuevos:
            partes[(p["fecha_informe"], p["texto"])] = p
        print(f"{dia}: {len(nuevos)} párrafos con evacuados")
        time.sleep(1)
    corte = (hoy - timedelta(days=120)).isoformat()
    lista = sorted((p for p in partes.values() if p["fecha_informe"] >= corte),
                   key=lambda p: (p["fecha_informe"], p["pais"]), reverse=True)
    ultimo = {}
    for p in lista:
        ultimo.setdefault(p["pais"], p)
    doc = {
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "fuente": "OPS/PAHO · Monitoreo de Amenazas Naturales (resume partes oficiales de cada país)",
        "nota": "Cifras tal como las informó cada organismo. DOTS no estima evacuados; un día sin parte queda sin dato.",
        "ultimo_por_pais": ultimo,
        "partes": lista,
        "dias_revisados": revisados,
        "dias_sin_parte": sin_parte,
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump(doc, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(f"{len(lista)} párrafos guardados; países con parte: {', '.join(ultimo) or 'ninguno'}")


if __name__ == "__main__":
    main()
