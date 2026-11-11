"""Gestor de Control de DOTS.

Corre en GitHub Actions (gestor-control.yml). No usa IA: lee las fichas de gestores/fichas.yml,
revisa la última corrida de cada tarea, la frescura de los datos de la rama `datos` y arma un
informe amplio en texto. Lo manda por Telegram y lo deja en el issue «Informe de gestores».

Modos:
  python scripts/gestor_control.py            informe completo
  python scripts/gestor_control.py --falla    aviso corto de una tarea que falló (lo usa gestor-fallas.yml)
  python scripts/gestor_control.py --prueba   sólo prueba Telegram y dice qué bot está conectado
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests
import yaml

REPO = os.environ.get("GITHUB_REPOSITORY", "Alvarorfontana/observatorio-agro")
GH = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
AHORA = datetime.now(timezone.utc)
SITIO = "https://observatorio-agro.vercel.app"


def gh(path, method="GET", **kw):
    h = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    r = requests.request(method, GH + path, headers=h, timeout=30, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def horas_desde(iso):
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (AHORA - t).total_seconds() / 3600
    except Exception:
        return None


def hace(h):
    if h is None:
        return "sin fecha"
    if h < 1:
        return "hace menos de 1 hora"
    if h < 48:
        return f"hace {h:.0f} h"
    return f"hace {h / 24:.0f} días"


def fecha_ar(iso):
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-3)))
        return t.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso or "s/d"


def leer_dato(path):
    """Lee un archivo de la rama datos (el workflow la trae con datos_rama.sh traer)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def fecha_dato(path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "origin/datos", "--", path],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return out or None
    except Exception:
        return None


# ---------------------------------------------------------------- secciones del informe

def seccion_gestores(fichas):
    lineas, problemas = [], []
    for clave, g in fichas.items():
        lineas.append(f"\n{g['nombre'].upper()} · {g['funcion']}")
        for t in g.get("tareas", []):
            wf, maxh = t["workflow"], t.get("max_horas")
            try:
                runs = gh(f"/repos/{REPO}/actions/workflows/{wf}/runs?per_page=1").get("workflow_runs", [])
            except Exception as e:
                lineas.append(f"  - {wf}: no se pudo consultar ({type(e).__name__})")
                continue
            if not runs:
                lineas.append(f"  - {wf}: nunca corrió")
                continue
            r = runs[0]
            nombre = r.get("name") or wf
            h = horas_desde(r.get("updated_at") or r.get("created_at"))
            res = r.get("conclusion") or r.get("status")
            estado = {"success": "bien", "failure": "FALLÓ", "cancelled": "cancelada",
                      "timed_out": "SE CORTÓ POR TIEMPO", "in_progress": "corriendo", "queued": "en cola"}.get(res, res)
            atrasada = maxh and h is not None and h > maxh
            marca = " · ATRASADA" if atrasada else ""
            lineas.append(f"  - {nombre}: {estado}, {hace(h)}{marca}")
            if res in ("failure", "timed_out") or atrasada:
                problemas.append(f"{nombre}: {estado}{marca} ({r.get('html_url')})")
    return lineas, problemas


def seccion_datos(fichas):
    lineas, problemas = [], []
    for path, maxh in (fichas.get("control", {}).get("datos_frescos") or {}).items():
        iso = fecha_dato(path)
        h = horas_desde(iso) if iso else None
        viejo = h is None or h > maxh
        lineas.append(f"  - {path.split('/')[-1]}: actualizado {hace(h)}{' · VIEJO' if viejo else ''}")
        if viejo:
            problemas.append(f"{path} sin actualizar ({hace(h)})")
    return lineas, problemas


def seccion_crecidas():
    est = leer_dato("data/avisos_estado.json")
    avi = leer_dato("data/avisos.json") or {}
    if not isinstance(est, dict):
        return ["  Sin datos de crecidas."]
    import re
    nombres_id = {}
    try:
        with open("cuenca.py", encoding="utf-8") as f:
            for i, lugar in re.findall(r"'id':\s*'([a-z0-9-]+)',\s*'river':\s*'[^']*',\s*'place':\s*'([^']+)'", f.read()):
                nombres_id[i] = lugar
    except Exception:
        pass
    nom = lambda i: nombres_id.get(i) or i.split("-", 1)[-1].replace("-", " ").title()
    por = {}
    for lid, v in est.items():
        por.setdefault((v or {}).get("level", "s/d"), []).append(lid)
    lineas = []
    for nivel in ("Evacuación", "Alerta", "Atención", "Normal"):
        ids = por.get(nivel, [])
        if not ids:
            continue
        nombres = ", ".join(sorted(nom(i) for i in ids))
        lineas.append(f"  {nivel} ({len(ids)}): {nombres if nivel != 'Normal' else 'resto de las localidades'}")
    cambios = [i for i in (avi.get("items") or []) if horas_desde(i.get("at", "")) is not None and horas_desde(i["at"]) <= 26]
    if cambios:
        lineas.append("  Cambios de las últimas 24 horas:")
        lineas += [f"   · {c.get('text')}" for c in cambios[:12]]
    else:
        lineas.append("  Sin cambios de nivel en las últimas 24 horas.")
    return lineas


def seccion_nino():
    d = leer_dato("data/enso_pronostico.json") or {}
    lineas = []
    cpc = d.get("cpc") or {}
    if cpc.get("estado") == "recibido":
        lineas.append(f"  NOAA CPC ({cpc.get('emitido')}): {cpc.get('alerta')}.")
        probs = cpc.get("probabilidades") or []
        if probs and isinstance(probs[0], dict):
            p = probs[0]
            partes = [f"{k} {v}%" for k, v in p.items() if isinstance(v, (int, float))]
            if partes:
                lineas.append(f"  Próximo trimestre ({p.get('trimestre') or p.get('season') or ''}): " + ", ".join(partes))
    mei = (d.get("mei") or {}).get("ultimo") or {}
    if mei:
        lineas.append("  MEI.v2 último: " + ", ".join(f"{k} {v}" for k, v in mei.items()))
    iri = d.get("ccsr_iri") or {}
    if iri.get("estado") != "recibido":
        lineas.append(f"  IRI Columbia: sin dato ({iri.get('motivo', 'no respondió')}).")
    n34 = leer_dato("data/nino34_diario.json")
    if isinstance(n34, dict):
        ult = n34.get("ultimo") or n34.get("latest") or {}
        if ult:
            lineas.append("  Niño 3.4 diario: " + ", ".join(f"{k} {v}" for k, v in ult.items() if not isinstance(v, (dict, list))))
    return lineas or ["  Sin datos de El Niño."]


def seccion_heladas():
    d = leer_dato("data/goes_heladas.json")
    if not isinstance(d, dict):
        return ["  Sin datos de heladas."]
    fp = d.get("frost_places") or []
    lin = [f"  Noche {d.get('night')}: {len(fp)} localidades con helada en superficie y {d.get('frost_cells', 0)} celdas de 0,5° bajo 0 °C (de {d.get('cells', '?')})."]
    if fp:
        lin.append("  Localidades: " + ", ".join(str(p.get("name", p)) if isinstance(p, dict) else str(p) for p in fp[:20]))
    return lin


def seccion_desmontes():
    d = leer_dato("data/desmonte_ndvi_reciente.json")
    if not isinstance(d, dict):
        return ["  Sin datos de desmontes."]
    res = d.get("resumen") or {}
    ha = res.get("ha_total") or {}
    niv = res.get("niveles") or {}
    lin = [f"  Corrida {str(d.get('generado', ''))[:10]} ({(d.get('antes') or {}).get('rotulo')} contra {(d.get('despues') or {}).get('rotulo')})."]
    if ha:
        lin.append("  Hectáreas por gravedad: " + ", ".join(f"{k} {v}" for k, v in ha.items()))
    if niv:
        lin.append("  Parches por gravedad: " + ", ".join(f"{k} {v}" for k, v in niv.items()))
    prov = res.get("provincias") or {}
    if prov:
        top = sorted(prov.items(), key=lambda kv: -(kv[1].get("ha", 0) if isinstance(kv[1], dict) else kv[1] or 0))[:5]
        lin.append("  Provincias: " + ", ".join(f"{k} {v.get('ha', v) if isinstance(v, dict) else v}" for k, v in top))
    ae = d.get("alphaearth") or {}
    if ae:
        cuenta = {}
        for p in d.get("parches") or []:
            r = (p.get("alphaearth") or {}).get("lectura")
            if r:
                cuenta[r] = cuenta.get(r, 0) + 1
        lin.append(f"  AlphaEarth {ae.get('anio_antes')} contra {ae.get('anio_despues')}: "
                   + (", ".join(f"{k} {v}" for k, v in cuenta.items()) or "sin parches evaluados"))
    cob = d.get("cobertura") or {}
    if cob.get("fallidas"):
        lin.append(f"  Ojo: {cob.get('fallidas')} de {cob.get('celdas')} celdas no se pudieron calcular.")
    return lin


def seccion_otros():
    lin = []
    for path, titulo in (("data/rinde_agua.json", "Rinde por agua"), ("data/focos_historia.json", "Historia de focos"),
                         ("data/barrios_radar.json", "Barrios por radar"), ("data/renabap_localidades.json", "RENABAP")):
        d = leer_dato(path)
        iso = fecha_dato(path)
        if d is None:
            lin.append(f"  {titulo}: sin datos.")
        else:
            extra = f", campaña {d.get('season')}" if isinstance(d, dict) and d.get("season") else ""
            lin.append(f"  {titulo}: actualizado {hace(horas_desde(iso)) if iso else 'sin fecha'}{extra}.")
    return lin


def seccion_sitio():
    lin = []
    for url, titulo in ((SITIO + "/", "Portada"), (SITIO + "/api/health", "API")):
        try:
            r = requests.get(url, timeout=25)
            lin.append(f"  {titulo}: responde ({r.status_code}).")
        except Exception as e:
            lin.append(f"  {titulo}: NO RESPONDE ({type(e).__name__}).")
    return lin


# ---------------------------------------------------------------- canales

def telegram_diagnostico():
    # El informe va a un chat privado (TELEGRAM_CONTROL_CHAT_ID), nunca al canal público de crecidas.
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok:
        return False, "Telegram sin configurar: falta el secreto TELEGRAM_BOT_TOKEN."
    try:
        me = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=20).json()
    except Exception as e:
        return False, f"Telegram no respondió ({type(e).__name__})."
    if not me.get("ok"):
        return False, "El token del bot no es válido (Telegram lo rechazó). Hay que generar uno nuevo con BotFather."
    bot = me["result"]
    if not chat:
        return False, (f"Bot conectado: @{bot.get('username')} ({bot.get('first_name')}), pero falta el secreto "
                       "TELEGRAM_CONTROL_CHAT_ID con tu chat privado para recibir el informe.")
    return True, f"Bot conectado: @{bot.get('username')} ({bot.get('first_name')}). Chat de destino: {chat}."


def telegram(texto):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return "sin configurar"
    partes, actual = [], ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) + 1 > 3900:
            partes.append(actual)
            actual = ""
        actual += linea + "\n"
    if actual.strip():
        partes.append(actual)
    for p in partes:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": p, "disable_web_page_preview": True}, timeout=30)
        j = r.json() if r.content else {}
        if not j.get("ok"):
            desc = j.get("description", f"HTTP {r.status_code}")
            if "chat not found" in desc:
                desc += " · El chat no existe o el bot nunca recibió un mensaje: abrí el bot en Telegram y tocá Iniciar (/start)."
            elif "not enough rights" in desc or "forbidden" in desc.lower():
                desc += " · Si es un canal, el bot tiene que ser administrador con permiso para publicar."
            return "falló: " + desc
    return f"enviado ({len(partes)} mensaje{'s' if len(partes) > 1 else ''})"


def correo(texto, asunto):
    """Manda el informe por mail con Resend (plan gratuito). La dirección va en el secreto CONTROL_EMAIL,
    nunca en el código: el repositorio es público."""
    key, dest = os.environ.get("RESEND_API_KEY"), os.environ.get("CONTROL_EMAIL")
    if not key or not dest:
        falta = [n for n, v in (("RESEND_API_KEY", key), ("CONTROL_EMAIL", dest)) if not v]
        return "sin configurar: falta " + " y ".join(falta)
    sender = os.environ.get("AVISOS_FROM") or "DOTS Campo <onboarding@resend.dev>"
    import html as _h
    cuerpo = ('<div style="font-family:Arial,sans-serif;font-size:14px;color:#101828">'
              '<pre style="font-family:Consolas,Menlo,monospace;font-size:13px;white-space:pre-wrap">'
              + _h.escape(texto) + "</pre></div>")
    try:
        r = requests.post("https://api.resend.com/emails", timeout=30,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"from": sender, "to": [d.strip() for d in dest.split(",") if d.strip()],
                                "subject": asunto, "html": cuerpo, "text": texto})
    except Exception as e:
        return f"falló ({type(e).__name__})"
    if r.ok:
        return "enviado"
    detalle = ""
    try:
        detalle = r.json().get("message", "")
    except Exception:
        pass
    return f"falló: HTTP {r.status_code} {detalle[:200]}"


def issue(texto):
    if not TOKEN:
        return "sin token"
    titulo = "Informe de gestores"
    try:
        abiertos = gh(f"/repos/{REPO}/issues?state=open&labels=informe-gestores&per_page=5")
        if abiertos:
            num = abiertos[0]["number"]
        else:
            num = gh(f"/repos/{REPO}/issues", "POST", json={
                "title": titulo, "labels": ["informe-gestores"],
                "body": "Acá el gestor de Control deja cada informe. Activá las notificaciones de este issue para recibirlos en la app de GitHub."})["number"]
        gh(f"/repos/{REPO}/issues/{num}/comments", "POST", json={"body": "```\n" + texto[:60000] + "\n```"})
        return f"publicado en el issue #{num}"
    except Exception as e:
        return f"falló ({type(e).__name__})"


# ---------------------------------------------------------------- modos

def informe():
    with open("gestores/fichas.yml", encoding="utf-8") as f:
        fichas = yaml.safe_load(f)
    g_lin, g_prob = seccion_gestores(fichas)
    d_lin, d_prob = seccion_datos(fichas)
    tg_ok, tg_diag = telegram_diagnostico()
    problemas = g_prob + d_prob
    hoy = fecha_ar(AHORA.isoformat())
    txt = [f"DOTS · INFORME DE GESTORES · {hoy} (hora argentina)", ""]
    txt.append("RESUMEN")
    txt.append("  Todo funcionó con normalidad." if not problemas else f"  {len(problemas)} punto(s) para revisar:")
    txt += [f"  - {p}" for p in problemas]
    txt += ["", "CRECIDAS · CUENCA DEL PLATA"] + seccion_crecidas()
    txt += ["", "EL NIÑO"] + seccion_nino()
    txt += ["", "HELADAS · GOES-19"] + seccion_heladas()
    txt += ["", "DESMONTES · NDVI SENTINEL-2"] + seccion_desmontes()
    txt += ["", "OTROS DATOS"] + seccion_otros()
    txt += ["", "SITIO WEB"] + seccion_sitio()
    txt += ["", "ESTADO DE CADA GESTOR"] + g_lin
    txt += ["", "FRESCURA DE LOS DATOS"] + d_lin
    txt += ["", "CANALES", "  Correo: por Resend al secreto CONTROL_EMAIL.", "  " + tg_diag, "",
            "Fuentes: GitHub Actions y rama datos del repositorio observatorio-agro. Los valores son los últimos guardados por cada tarea; no se completan datos faltantes."]
    texto = "\n".join(txt)
    print(texto)
    avisos = fichas.get("control", {}).get("avisos", {})
    r_tg = telegram(texto) if avisos.get("telegram", True) and tg_ok else ("no enviado: " + tg_diag)
    asunto = f"DOTS · Informe de gestores {hoy[:10]}" + (f" · {len(problemas)} para revisar" if problemas else " · todo en orden")
    r_ma = correo(texto, asunto) if avisos.get("correo", True) else "desactivado"
    r_is = issue(texto + f"\n\nCorreo: {r_ma}\nTelegram: {r_tg}") if avisos.get("github_issue", True) else "desactivado"
    print(f"\nCorreo: {r_ma}\nTelegram: {r_tg}\nIssue: {r_is}")
    os.makedirs("data", exist_ok=True)
    with open("data/control.json", "w", encoding="utf-8") as f:
        json.dump({"generado": AHORA.isoformat(), "problemas": problemas, "correo": r_ma, "telegram": r_tg, "issue": r_is, "texto": texto}, f, ensure_ascii=False, indent=1)


def falla():
    nombre = os.environ.get("RUN_NAME", "Tarea")
    url = os.environ.get("RUN_URL", "")
    res = os.environ.get("RUN_CONCLUSION", "failure")
    estado = "se cortó por tiempo" if res == "timed_out" else "falló"
    texto = f"DOTS · AVISO DEL GESTOR DE CONTROL\n\nLa tarea «{nombre}» {estado} ({fecha_ar(AHORA.isoformat())}, hora argentina).\nDetalle: {url}"
    print(texto)
    print("Correo:", correo(texto, f"DOTS · Falló «{nombre}»"))
    ok, diag = telegram_diagnostico()
    print("Telegram:", telegram(texto) if ok else diag)


def prueba():
    print("Correo:", correo("DOTS · Prueba del gestor de Control.\nSi recibís este mail, el informe diario te va a llegar acá.",
                            "DOTS · Prueba del gestor de Control"))
    ok, diag = telegram_diagnostico()
    print(diag)
    if ok:
        print("Envío:", telegram("DOTS · Prueba del gestor de Control.\nSi recibís este mensaje, el bot quedó conectado al observatorio."))


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    {"--falla": falla, "--prueba": prueba}.get(modo, informe)()
