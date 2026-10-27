"""El Niño: pronósticos y fuentes oficiales con números, para la web y los avisos.

Junta, una vez por día, lo que DOTS antes sólo enlazaba:
  1. Probabilidades oficiales NOAA CPC (La Niña / Neutral / El Niño por trimestre). Desde febrero de 2026 NOAA
     clasifica con el RONI (índice relativo), no con el ONI. Página HTML; se lee la tabla y se valida que cada fila
     sume 100 %.
  2. Pronóstico CCSR/IRI (Universidad de Columbia): probabilidades por trimestre y gráficos de la pluma y de la
     intensidad. Se leen las probabilidades si la tabla está; si no, quedan sólo los gráficos.
  3. MEI.v2 de NOAA PSL: índice multivariado (océano y atmósfera), bimestral.
  4. Pronóstico estacional de lluvia y temperatura por localidad (ECMWF SEAS5 vía Open-Meteo, sin clave):
     anomalía mensual para los próximos meses en las 34 localidades ribereñas.
Nada se inventa: si una fuente no responde o cambia de formato, queda anotada como «sin dato» con el motivo.

Salida: data/enso_pronostico.json (rama datos).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

UA = {"User-Agent": "DOTS observatorio (datos abiertos; contacto en observatorio-agro.vercel.app)"}
CPC_PROBS = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/probabilities/"
CPC_PROBS_IMG = "https://www.cpc.ncep.noaa.gov/archives/enso/roni/images/{y}/enso-probs-current.png"
CPC_DISC = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
CCSR = "https://forecast.ccsr.columbia.edu/forecasts/enso/forecast"
CCSR_IMG = {"probabilidades": "https://ensoforecast.iri.columbia.edu/figure3_plot/{y}/{m}",
            "intensidad": "https://ensoforecast.iri.columbia.edu/strength_plot/{y}/{m}"}
MEI = "https://psl.noaa.gov/enso/mei/data/meiv2.data"
SEASONAL = "https://seasonal-api.open-meteo.com/v1/seasonal"
SEASONS = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
MONTHS_EN = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August",
                                         "September", "October", "November", "December"), start=1)}


def get(url, **kw):
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=40, headers=UA, **kw)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = type(exc).__name__
        time.sleep(4 * (attempt + 1))
    raise RuntimeError(last or "sin respuesta")


def html_text(html):
    """Texto plano de una página HTML: sin scripts ni etiquetas, celdas separadas por espacios."""
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)</(td|th|tr|p|div|li|h\d)>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def parse_season_probs(text):
    """Filas «TRIMESTRE … La Niña Neutral El Niño» en porcentaje. Sólo se aceptan filas que suman 100 ± 2."""
    rows, seen = [], set()
    pat = re.compile(r"\b(" + "|".join(SEASONS) + r")\b[^\d\n]{0,60}?(?:\b(20\d\d)(?:[-/](\d{2,4}))?\b[^\d\n]{0,20}?)?"
                     r"(\d{1,3})\s*%?\s+(\d{1,3})\s*%?\s+(\d{1,3})\s*%?")
    for line in text.splitlines():
        line = " ".join(line.split())
        for m in pat.finditer(line):
            season = m.group(1)
            nina, neutral, nino = int(m.group(4)), int(m.group(5)), int(m.group(6))
            if abs(nina + neutral + nino - 100) > 2 or season in seen:
                continue
            seen.add(season)
            rows.append({"season": season, "year": int(m.group(2)) if m.group(2) else None,
                         "la_nina": nina, "neutral": neutral, "el_nino": nino})
    # la tabla también aparece en celdas de una línea cada una: unir y reintentar
    if len(rows) < 3:
        flat = " ".join(text.split())
        rows2, seen2 = [], set()
        for m in pat.finditer(flat):
            s = m.group(1)
            a, b, c = int(m.group(4)), int(m.group(5)), int(m.group(6))
            if abs(a + b + c - 100) <= 2 and s not in seen2:
                seen2.add(s)
                rows2.append({"season": s, "year": int(m.group(2)) if m.group(2) else None,
                              "la_nina": a, "neutral": b, "el_nino": c})
        if len(rows2) > len(rows):
            rows = rows2
    if len(rows) < 3:
        raise ValueError("no se encontró la tabla de probabilidades")
    return rows


def issue_month(text):
    m = re.search(r"(?:Issued|Released|Published|Forecast)[^A-Za-z]{0,10}(?:on\s+)?(" + "|".join(MONTHS_EN) + r")\s+(\d{1,2},\s*)?(20\d\d)", text)
    if not m:
        m = re.search(r"\b(" + "|".join(MONTHS_EN) + r")\s+(\d{1,2},\s*)?(20\d\d)\b", text)
    return f"{m.group(3)}-{MONTHS_EN[m.group(1)]:02d}" if m else None


def cpc():
    r = get(CPC_PROBS)
    text = html_text(r.text)
    rows = parse_season_probs(text)
    issued = issue_month(text)
    y = (issued or str(datetime.now(timezone.utc).year))[:4]
    out = {"estado": "recibido", "fuente": "NOAA Climate Prediction Center", "url": CPC_PROBS,
           "emitido": issued, "indice": "RONI", "probabilidades": rows, "grafico": CPC_PROBS_IMG.format(y=y),
           "nota": ("Probabilidades oficiales de NOAA. Desde febrero de 2026 NOAA clasifica El Niño y La Niña con el "
                    "RONI (índice relativo), que descuenta el calentamiento general del océano.")}
    try:
        d = html_text(get(CPC_DISC).text)
        m = re.search(r"ENSO Alert System Status:\s*([^\n]{3,120})", d)
        s = re.search(r"Synopsis:\s*([^\n]{20,600})", d)
        out["alerta"] = " ".join(m.group(1).split()) if m else None
        out["sinopsis"] = " ".join(s.group(1).split()) if s else None
    except RuntimeError:
        pass
    return out


def ccsr():
    now = datetime.now(timezone.utc)
    out = {"estado": "sin dato", "fuente": "CCSR/IRI · Universidad de Columbia", "url": CCSR, "probabilidades": []}
    try:
        text = html_text(get(CCSR).text)
        out["emitido"] = issue_month(text)
        try:
            out["probabilidades"] = parse_season_probs(text)
            out["estado"] = "recibido"
        except ValueError as exc:
            out["motivo"] = str(exc)
        m = re.search(r"(\d{1,2})\s+(?:dynamical)[^\n]{0,40}?(\d{1,2})\s+statistical", text, re.I)
        if m:
            out["modelos"] = {"dinamicos": int(m.group(1)), "estadisticos": int(m.group(2))}
    except RuntimeError as exc:
        out["motivo"] = f"no respondió ({exc})"
    y, mth = (out.get("emitido") or f"{now.year}-{now.month:02d}").split("-")
    out["graficos"] = {k: v.format(y=y, m=int(mth)) for k, v in CCSR_IMG.items()}
    return out


def parse_mei(text):
    pts = []
    for line in text.splitlines():
        cols = line.split()
        if len(cols) != 13:
            continue
        try:
            year = int(cols[0])
            vals = [float(v) for v in cols[1:]]
        except ValueError:
            continue
        if not 1979 <= year <= 2100:
            continue
        for i, v in enumerate(vals):
            if -10 < v < 10 and v > -99:
                pts.append({"bimestre": f"{year}-{i + 1:02d}", "mei": v})
    if len(pts) < 120:
        raise ValueError("serie MEI.v2 incompleta")
    return pts


def mei():
    BIM = ("DE", "EF", "FM", "MA", "AM", "MJ", "JJ", "JA", "AS", "SO", "ON", "ND")
    pts = parse_mei(get(MEI).text)
    last = pts[-1]
    return {"estado": "recibido", "fuente": "NOAA Physical Sciences Laboratory", "url": MEI,
            "ultimo": dict(last, nombre=BIM[int(last["bimestre"][5:]) - 1] + " " + last["bimestre"][:4]),
            "serie": pts[-60:],
            "nota": ("MEI.v2: combina temperatura del mar, presión, vientos y nubosidad del Pacífico tropical. "
                     "Valores de +0,5 o más indican condiciones de El Niño; -0,5 o menos, de La Niña.")}


SEASONAL_CANDIDATES = [
    ("monthly", ["precipitation_anomaly", "temperature_2m_anomaly"]),
    ("monthly", ["precipitation_mean_anomaly", "temperature_2m_mean_anomaly"]),
    ("weekly", ["precipitation_anomaly", "temperature_2m_anomaly"]),
]


def seasonal_point(lat, lon, plan=None):
    """Anomalías estacionales para un punto. Devuelve (plan usado, datos)."""
    last = None
    for agg, vars_ in ([plan] if plan else SEASONAL_CANDIDATES):
        try:
            r = requests.get(SEASONAL, params={"latitude": lat, "longitude": lon, agg: ",".join(vars_),
                                               "timezone": "America/Argentina/Buenos_Aires"}, timeout=40, headers=UA)
        except requests.RequestException as exc:
            last = type(exc).__name__
            continue
        if r.status_code != 200:
            try:
                last = r.json().get("reason", f"HTTP {r.status_code}")
            except ValueError:
                last = f"HTTP {r.status_code}"
            continue
        d = r.json().get(agg) or {}
        if d.get("time") and any(v.startswith("precipitation") for v in d):
            return (agg, vars_), d
        last = "respuesta sin la variable pedida"
    raise RuntimeError(last or "sin respuesta")


def seasonal():
    import cuenca
    places, plan, errors = [], None, {}
    for st in cuenca.STATIONS:
        try:
            plan, d = seasonal_point(st["lat"], st["lon"], plan)
        except RuntimeError as exc:
            errors[st["place"]] = str(exc)[:160]
            continue
        pvar = next(k for k in d if k.startswith("precipitation"))
        tvar = next((k for k in d if k.startswith("temperature")), None)
        months = []
        for i, t in enumerate(d["time"][:7]):
            months.append({"mes": t[:7], "lluvia_anomalia_mm": d[pvar][i],
                           "temp_anomalia_c": d[tvar][i] if tvar else None})
        places.append({"id": st["id"], "place": st["place"], "river": st["river"], "meses": months,
                       "unidad_lluvia": "mm (anomalía del mes respecto del clima del modelo)"})
    out = {"estado": "recibido" if places else "sin dato", "fuente": "ECMWF SEAS5 vía Open-Meteo",
           "url": SEASONAL, "parametros": {"agregado": plan[0], "variables": plan[1]} if plan else None,
           "localidades": places,
           "nota": ("Pronóstico estacional: anomalía de lluvia y temperatura de cada mes frente a lo normal del modelo. "
                    "Es una tendencia probable para la zona, no un pronóstico del tiempo de un día.")}
    if errors:
        out["errores"] = errors
    return out


def run_all():
    data = {"actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    for key, fn in (("cpc", cpc), ("ccsr_iri", ccsr), ("mei", mei), ("estacional", seasonal)):
        try:
            data[key] = fn()
        except Exception as exc:  # una fuente caída no frena a las demás
            data[key] = {"estado": "sin dato", "motivo": f"{type(exc).__name__}: {str(exc)[:200]}"}
        e = data[key]
        print(f"{key}: {e.get('estado')} {e.get('motivo', '')}"
              + (f" · {len(e.get('probabilidades', []))} trimestres" if 'probabilidades' in e else "")
              + (f" · {len(e.get('localidades', []))} localidades {e.get('parametros')}" if 'localidades' in e else ""),
              flush=True)
    return data


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "enso_pronostico.json")
    data = run_all()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
