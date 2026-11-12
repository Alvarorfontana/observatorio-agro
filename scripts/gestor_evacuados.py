"""Gestor de evacuados de DOTS.

Corre una vez por semana en GitHub Actions (gestor-evacuados.yml). No usa IA.

Qué hace:
  1. Lee los lugares de gestores/evacuados.yml: países, provincias o estados y municipios de la Cuenca del Plata
     (Argentina, Uruguay, Paraguay y Brasil).
  2. Para cada lugar busca en Google Noticias (RSS público, gratuito y sin clave) las notas de los últimos 7 días
     con palabras como «evacuados», «autoevacuados», «desplazados», «desabrigados» o «desalojados». Además busca
     en el sitio de cada organismo oficial (SINAGIR, gobiernos provinciales, SINAE, SEN, Defesa Civil) y en GDELT,
     una segunda red de noticias, también gratuita y sin clave.
  3. Saca las cifras que aparecen en el titular (por ejemplo «468 evacuados», «63 familias»). No calcula ni estima:
     cada parte queda «a verificar» con su medio y su enlace.
  4. Guarda todo en la rama datos (data/evacuados_partes.json y un histórico) y manda el informe por correo
     (Resend, si están los secretos) y al issue «Partes de evacuados» de GitHub.

No existe una base pública y automática de evacuados en ninguno de los cuatro países: los organismos (SINAGIR,
Defensa Civil de cada provincia, SINAE y los Cecoed, la SEN, la Defesa Civil de cada estado) publican partes
sueltos. Por eso este gestor junta lo que sale en la prensa y en los comunicados, y deja marcados los lugares sin
novedades.

Uso:
  python scripts/gestor_evacuados.py              corrida completa
  python scripts/gestor_evacuados.py --sin-envio  junta y guarda, pero no manda correo ni issue
"""
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUGARES = os.path.join(RAIZ, "gestores", "evacuados.yml")
SALIDA = os.path.join(RAIZ, "data", "evacuados_partes.json")
HISTORICO = os.path.join(RAIZ, "data", "evacuados_historico.json")
REPO = os.environ.get("GITHUB_REPOSITORY", "Alvarorfontana/observatorio-agro")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DIAS = 7
MAX_HISTORICO = 5000
PAUSA = 1.0  # segundos entre pedidos, para no saturar el servicio

# Palabras que acompañan a una cifra de personas o familias fuera de su casa, en español y en portugués.
CLASES = {
    "autoevacuados": r"auto-?evacuad[oa]s",
    "evacuados": r"evacuad[oa]s",
    "desplazados": r"desplazad[oa]s",
    "damnificados": r"damnificad[oa]s",
    "desabrigados": r"desabrigad[oa]s",
    "desalojados": r"desalojad[oa]s",
    "familias": r"familias",
    "hogares": r"hogares",
    "personas": r"personas|pessoas",
}
NUMERO = r"(\d{1,3}(?:[.,]\d{3})+|\d+)"
PATRON = re.compile(
    NUMERO + r"\s+(?:de\s+)?(?:personas\s+|pessoas\s+)?(" + "|".join(CLASES.values()) + r")",
    re.IGNORECASE,
)


def a_entero(txt):
    """'1.537' o '1,537' → 1537. Los separadores de miles van con punto o coma."""
    return int(re.sub(r"[.,]", "", txt))


def clase_de(palabra):
    p = palabra.lower()
    for nombre, rx in CLASES.items():
        if re.fullmatch(rx, p, re.IGNORECASE):
            return nombre
    return p


def cifras(texto):
    """Devuelve las cifras que aparecen junto a una palabra de evacuación, sin repetir.
    Ej.: '468 evacuados y 1.537 autoevacuados' → [{'cifra': 468, 'que': 'evacuados'}, {'cifra': 1537, 'que': 'autoevacuados'}]"""
    vistas, out = set(), []
    for m in PATRON.finditer(texto or ""):
        n = a_entero(m.group(1))
        if n < 1 or n > 2_000_000:
            continue
        que = clase_de(m.group(2))
        if (n, que) in vistas:
            continue
        vistas.add((n, que))
        out.append({"cifra": n, "que": que})
    return out


def consulta(lugar, palabras):
    ors = " OR ".join(f'"{p}"' if " " in p else p for p in palabras)
    return f'"{lugar}" ({ors}) when:{DIAS}d'


def url_rss(q, google):
    return ("https://news.google.com/rss/search?q=" + quote(q)
            + f"&hl={google['hl']}&gl={google['gl']}&ceid={quote(google['ceid'])}")


def leer_rss(xml_texto):
    """Lee un RSS de Google Noticias y devuelve [{titulo, enlace, medio, fecha}]."""
    items = []
    raiz = ET.fromstring(xml_texto)
    for it in raiz.iter("item"):
        titulo = html.unescape((it.findtext("title") or "").strip())
        medio = (it.findtext("source") or "").strip()
        if medio and titulo.endswith(" - " + medio):
            titulo = titulo[: -len(" - " + medio)]
        fecha = None
        try:
            fecha = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            pass
        desc = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        items.append({"titulo": titulo, "enlace": (it.findtext("link") or "").strip(),
                      "medio": medio, "fecha": fecha, "texto": desc})
    return items


def lugares(cfg):
    """Recorre la lista del más específico al más general, para que un parte quede en el lugar más preciso."""
    out = []
    for pais, p in cfg["paises"].items():
        idioma = p["idioma"]
        for prov, d in p["provincias"].items():
            for muni in d.get("municipios") or []:
                out.append({"pais": pais, "provincia": prov, "lugar": muni, "nivel": "municipio",
                            "rio": d.get("rio"), "idioma": idioma})
    for pais, p in cfg["paises"].items():
        for prov, d in p["provincias"].items():
            nombre = re.sub(r"\s*\((PY|BR)\)$", "", prov)
            out.append({"pais": pais, "provincia": prov, "lugar": nombre, "nivel": "provincia",
                        "rio": d.get("rio"), "idioma": p["idioma"]})
    for pais, p in cfg["paises"].items():
        for org in p.get("nacional") or []:
            out.append({"pais": pais, "provincia": None, "lugar": org, "nivel": "pais",
                        "rio": None, "idioma": p["idioma"]})
    return out


def leer_gdelt(json_texto):
    """Lee la respuesta de la API DOC de GDELT y devuelve [{titulo, enlace, medio, fecha}]."""
    try:
        j = json.loads(json_texto)
    except ValueError:
        return []  # GDELT responde texto plano cuando la consulta no le gusta
    items = []
    for a in j.get("articles") or []:
        fecha = None
        try:
            fecha = datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        items.append({"titulo": html.unescape(a.get("title") or "").strip(), "enlace": a.get("url") or "",
                      "medio": a.get("domain") or "", "fecha": fecha, "texto": ""})
    return items


def url_gdelt(palabras, pais_fuente):
    q = "(" + " OR ".join(palabras) + f") sourcecountry:{pais_fuente}"
    return ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + quote(q)
            + f"&mode=artlist&format=json&maxrecords=250&timespan={DIAS}d&sort=datedesc")


def buscar_lugar(titulo, pais, lus):
    """Para notas de GDELT: el lugar más específico de la lista que aparece en el titular."""
    t = titulo.lower()
    for lu in lus:  # ya vienen del más específico al más general
        if lu["pais"] == pais and lu["nivel"] != "pais" and re.search(r"\b" + re.escape(lu["lugar"].lower()) + r"\b", t):
            return lu
    return {"pais": pais, "provincia": None, "lugar": pais, "nivel": "pais", "rio": None}


def busquedas(cfg):
    """Arma todas las búsquedas: por lugar, por sitio oficial y en GDELT."""
    out = []
    lus = lugares(cfg)
    for lu in lus:
        idi = cfg["idiomas"][lu["idioma"]]
        out.append({"url": url_rss(consulta(lu["lugar"], idi["palabras"]), idi["google"]), "leer": leer_rss,
                    "lugar": lu, "origen": "prensa", "motor": "Google Noticias"})
    for pais, orgs in (cfg.get("oficiales") or {}).items():
        idi = cfg["idiomas"][cfg["paises"][pais]["idioma"]]
        ors = " OR ".join(f'"{x}"' if " " in x else x for x in idi["palabras"])
        for o in orgs:
            prov = None if o["jurisdiccion"] == "Nación" else o["jurisdiccion"]
            lu = {"pais": pais, "provincia": prov, "lugar": o["organismo"], "nivel": "oficial", "rio": None}
            q = f"site:{o['dominio']} ({ors}) when:{DIAS}d"
            out.append({"url": url_rss(q, idi["google"]), "leer": leer_rss, "lugar": lu, "origen": "oficial",
                        "motor": "Google Noticias (sitio oficial)", "dominio": o["dominio"]})
    for pais, g in (cfg.get("gdelt") or {}).items():
        out.append({"url": url_gdelt(g["palabras"], g["pais_fuente"]), "leer": leer_gdelt,
                    "lugar": None, "pais": pais, "origen": "prensa", "motor": "GDELT"})
    return out, lus


def juntar(cfg, desde, traer=None):
    """Corre todas las búsquedas y arma la lista de partes nuevos (sin repetir enlaces ni titulares)."""
    s = requests.Session()
    s.headers["User-Agent"] = "DOTS-gestor-evacuados/1.0 (+https://observatorio-agro.vercel.app)"

    def traer_http(url):
        r = s.get(url, timeout=30)
        r.raise_for_status()
        return r.text

    pausa = PAUSA if traer is None else 0
    traer = traer or traer_http
    partes, vistos, errores, sin_partes, oficiales_sin = [], set(), [], [], []
    lista, lus = busquedas(cfg)
    for b in lista:
        nombre = b["lugar"]["lugar"] if b["lugar"] else f"GDELT {b['pais']}"
        try:
            items = b["leer"](traer(b["url"]))
        except Exception as e:
            errores.append(f"{nombre}: {type(e).__name__}")
            continue
        nuevos = 0
        for it in items:
            if it["fecha"] and it["fecha"] < desde:
                continue
            clave = re.sub(r"\W+", " ", it["titulo"].lower()).strip()
            if not it["titulo"] or it["enlace"] in vistos or clave in vistos:
                continue
            nums = cifras(it["titulo"] + " " + it["texto"])
            if not nums:
                continue  # sin cifra no es un parte: suele ser una nota de contexto
            lu = b["lugar"] or buscar_lugar(it["titulo"], b["pais"], lus)
            vistos.update({it["enlace"], clave})
            nuevos += 1
            partes.append({
                "fecha": it["fecha"].strftime("%Y-%m-%d") if it["fecha"] else None,
                "pais": lu["pais"], "provincia": lu["provincia"], "lugar": lu["lugar"],
                "nivel": lu["nivel"], "rio": lu.get("rio"), "origen": b["origen"], "motor": b["motor"],
                "titulo": it["titulo"], "medio": it["medio"], "enlace": it["enlace"],
                "cifras": nums, "estado": "a verificar",
            })
        if nuevos == 0 and b["lugar"]:
            if b["origen"] == "oficial":
                oficiales_sin.append(f"{b['lugar']['lugar']} ({b['dominio']})")
            elif b["lugar"]["nivel"] != "pais":
                sin_partes.append(f"{b['lugar']['lugar']} ({b['lugar']['pais']})")
        if pausa:
            time.sleep(pausa)
    partes.sort(key=lambda p: (p["pais"], p["provincia"] or "", p["fecha"] or ""))
    return partes, sin_partes, oficiales_sin, errores


def texto_cifras(nums):
    return ", ".join(f"{n['cifra']:,}".replace(",", ".") + f" {n['que']}" for n in nums)


def informe(partes, sin_partes, errores, desde, hasta, oficiales_sin=()):
    lineas = [
        "DOTS · Partes de evacuados de la Cuenca del Plata",
        f"Semana del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}",
        "",
        "Fuente: notas y comunicados indexados por Google Noticias. Las cifras salen del titular o del resumen",
        "de cada nota y están a verificar en el enlace antes de usarlas. DOTS no estima evacuados.",
        "",
        f"Partes nuevos con cifras: {len(partes)}",
    ]
    for pais in ("Argentina", "Uruguay", "Paraguay", "Brasil"):
        del_pais = [p for p in partes if p["pais"] == pais]
        lineas += ["", pais.upper(), "-" * len(pais)]
        if not del_pais:
            lineas.append("Sin partes nuevos esta semana.")
            continue
        provs = []
        for p in del_pais:
            if p["provincia"] not in provs:
                provs.append(p["provincia"])
        for prov in provs:
            lineas.append(f"{prov or 'Nivel nacional'}:")
            for p in [x for x in del_pais if x["provincia"] == prov]:
                fecha = datetime.strptime(p["fecha"], "%Y-%m-%d").strftime("%d/%m") if p["fecha"] else "s/f"
                marca = " [sitio oficial]" if p.get("origen") == "oficial" else ""
                lineas.append(f"  {fecha} · {p['lugar']}{marca} · {texto_cifras(p['cifras'])}")
                lineas.append(f"         {p['titulo']} ({p['medio'] or 's/medio'})")
                lineas.append(f"         {p['enlace']}")
    if sin_partes:
        lineas += ["", "Lugares sin partes nuevos con cifras (puede no haber evacuados o no haberse publicado):",
                   "  " + ", ".join(sin_partes)]
    if oficiales_sin:
        lineas += ["", "Organismos oficiales sin partes con cifras en su sitio esta semana:",
                   "  " + "; ".join(oficiales_sin)]
    if errores:
        lineas += ["", "Búsquedas que fallaron:", "  " + "; ".join(errores)]
    lineas += ["", "Para sumar lugares: gestores/evacuados.yml. Planilla de seguimiento: hoja «Partes»."]
    return "\n".join(lineas)


def correo(texto, asunto):
    key, dest = os.environ.get("RESEND_API_KEY"), os.environ.get("CONTROL_EMAIL")
    if not key or not dest:
        falta = [n for n, v in (("RESEND_API_KEY", key), ("CONTROL_EMAIL", dest)) if not v]
        return "sin configurar: falta " + " y ".join(falta)
    sender = os.environ.get("AVISOS_FROM") or "DOTS Campo <onboarding@resend.dev>"
    cuerpo = ('<div style="font-family:Arial,sans-serif;font-size:14px;color:#101828">'
              '<pre style="font-family:Consolas,Menlo,monospace;font-size:13px;white-space:pre-wrap">'
              + html.escape(texto) + "</pre></div>")
    try:
        r = requests.post("https://api.resend.com/emails", timeout=30,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"from": sender, "to": [d.strip() for d in dest.split(",") if d.strip()],
                                "subject": asunto, "html": cuerpo, "text": texto})
    except Exception as e:
        return f"falló ({type(e).__name__})"
    return "enviado" if r.ok else f"falló: HTTP {r.status_code}"


def issue(texto):
    if not TOKEN:
        return "sin token"
    h = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {TOKEN}"}
    api = f"https://api.github.com/repos/{REPO}"
    try:
        r = requests.get(f"{api}/issues?state=open&labels=partes-evacuados&per_page=5", headers=h, timeout=30)
        r.raise_for_status()
        abiertos = r.json()
        if abiertos:
            num = abiertos[0]["number"]
        else:
            r = requests.post(f"{api}/issues", headers=h, timeout=30, json={
                "title": "Partes de evacuados", "labels": ["partes-evacuados"],
                "body": "Acá el gestor de evacuados deja el informe de cada semana. Activá las notificaciones "
                        "de este issue para recibirlo en el correo o en la app de GitHub."})
            r.raise_for_status()
            num = r.json()["number"]
        r = requests.post(f"{api}/issues/{num}/comments", headers=h, timeout=30,
                          json={"body": "```\n" + texto[:60000] + "\n```"})
        r.raise_for_status()
        return f"publicado en el issue #{num}"
    except Exception as e:
        return f"falló ({type(e).__name__})"


def guardar_historico(partes):
    try:
        with open(HISTORICO, encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        hist = []
    enlaces = {p["enlace"] for p in hist}
    hist += [p for p in partes if p["enlace"] not in enlaces]
    hist = sorted(hist, key=lambda p: p.get("fecha") or "", reverse=True)[:MAX_HISTORICO]
    with open(HISTORICO, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    return len(hist)


def main():
    import yaml  # sólo para leer la lista de lugares; así las pruebas corren sin PyYAML
    sin_envio = "--sin-envio" in sys.argv
    with open(LUGARES, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    hasta = datetime.now(timezone.utc)
    desde = hasta - timedelta(days=DIAS)
    partes, sin_partes, oficiales_sin, errores = juntar(cfg, desde)
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({"actualizado": hasta.strftime("%Y-%m-%dT%H:%MZ"), "desde": desde.strftime("%Y-%m-%d"),
                   "fuente": "Google Noticias (RSS, incluida la búsqueda en sitios oficiales) y GDELT. Cifras a verificar en cada enlace.",
                   "partes": partes, "sin_partes": sin_partes, "oficiales_sin_partes": oficiales_sin,
                   "errores": errores},
                  f, ensure_ascii=False, indent=1)
    total = guardar_historico(partes)
    texto = informe(partes, sin_partes, errores, desde, hasta, oficiales_sin)
    print(texto)
    print(f"\nHistórico: {total} partes guardados.")
    if sin_envio:
        return
    asunto = f"DOTS · Partes de evacuados {hasta:%d/%m/%Y} · {len(partes)} nuevos"
    print("Correo:", correo(texto, asunto))
    print("Issue:", issue(texto))
    total_lugares = len(busquedas(cfg)[0])
    if len(errores) > total_lugares / 2:
        sys.exit(f"Fallaron {len(errores)} de {total_lugares} búsquedas.")


if __name__ == "__main__":
    main()
