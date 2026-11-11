"""Conteo de ganado gratis: RF-DETR (Apache 2.0) + recorte en mosaico (SAHI) en GitHub Actions, sin GPU paga.

Reemplaza, para fotos y videos cortos, al trabajador de RunPod (pago) que dejó en pausa la visión ganadera.

Qué hace
  · Foto (JPG/PNG), por ejemplo de drone: la corta en cuadros de 640 px que se pisan un poco, detecta en cada uno y
    junta los resultados. Así aparecen los animales chicos que en la foto entera se pierden (método SAHI).
  · Video (MP4/MOV): toma hasta 90 cuadros repartidos, cuenta en cada uno y sigue a los animales entre cuadros con
    ByteTrack (paquete trackers de Roboflow) para estimar cuántos distintos pasaron.
  · Deja la foto marcada y un JSON en data/conteo_ganado/, y si están los secretos manda el resultado por correo.

Modelo: RF-DETR Nano entrenado con COCO (clases vaca, oveja y caballo). No está entrenado con rodeos argentinos:
es un conteo de referencia, no un inventario. Ver docs y límites en DOTS-v3.0-CONTEO-GANADO.md.

Entrada (variables de entorno)
  CONTEO_URL      enlace directo a la foto o el video (también acepta enlaces de Google Drive compartidos)
  CONTEO_ESPECIE  vaca | oveja | caballo | todas   (por defecto vaca)
  CONTEO_MOSAICO  si | no                           (por defecto si; en fotos de celular a ras del suelo conviene no)
  CONTEO_UMBRAL   confianza mínima, 0 a 1           (por defecto 0.4)
"""
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "conteo_ganado")

# Identificadores COCO (los que devuelve RF-DETR preentrenado)
ESPECIES = {"caballo": 19, "oveja": 20, "vaca": 21}
NOMBRE = {v: k for k, v in ESPECIES.items()}
VIDEO = (".mp4", ".mov", ".m4v", ".avi", ".mkv")
MAX_CUADROS = 90
MAX_MB = 200

# Rangos de lectura de la confianza promedio
RANGOS_CONFIANZA = [
    (0.70, "alta", "el modelo reconoce bien a los animales"),
    (0.50, "media", "revisar la foto marcada: puede haber animales de más o de menos"),
    (0.0, "baja", "imagen difícil (lejos, de noche, tapados): tomar el número como orientativo"),
]


def lectura_confianza(c):
    for u, r, t in RANGOS_CONFIANZA:
        if c >= u:
            return r, t
    return RANGOS_CONFIANZA[-1][1], RANGOS_CONFIANZA[-1][2]


def clases_de(especie):
    especie = (especie or "vaca").strip().lower()
    if especie in ("todas", "todos"):
        return sorted(ESPECIES.values())
    if especie not in ESPECIES:
        raise SystemExit(f"Especie desconocida: {especie}. Usar vaca, oveja, caballo o todas.")
    return [ESPECIES[especie]]


def url_directa(url):
    """Convierte un enlace compartido de Google Drive en uno de descarga directa."""
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=download&)?id=)([\w-]{20,})", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def es_video(nombre, tipo=""):
    return nombre.lower().endswith(VIDEO) or tipo.startswith("video/")


def resumen_video(por_cuadro, unicos):
    """por_cuadro: conteos por cuadro muestreado; unicos: animales distintos según el seguimiento."""
    if not por_cuadro:
        return {"cuadros": 0, "maximo_en_un_cuadro": 0, "mediana_por_cuadro": 0, "distintos_estimados": 0}
    orden = sorted(por_cuadro)
    n = len(orden)
    med = orden[n // 2] if n % 2 else (orden[n // 2 - 1] + orden[n // 2]) / 2
    return {"cuadros": n, "maximo_en_un_cuadro": max(orden), "mediana_por_cuadro": med,
            "distintos_estimados": max(unicos, max(orden))}


def descargar(url, carpeta):
    import requests
    r = requests.get(url_directa(url), stream=True, timeout=120, headers={"User-Agent": "DOTS-Campo/1.0"})
    r.raise_for_status()
    tipo = r.headers.get("Content-Type", "")
    if "text/html" in tipo:
        raise SystemExit("El enlace devuelve una página y no un archivo. En Drive: Compartir → cualquier persona con el enlace.")
    nombre = os.path.basename(url.split("?")[0]) or "archivo"
    if not os.path.splitext(nombre)[1]:
        nombre += ".mp4" if tipo.startswith("video/") else ".jpg"
    ruta = os.path.join(carpeta, nombre)
    total = 0
    with open(ruta, "wb") as f:
        for parte in r.iter_content(1 << 20):
            total += len(parte)
            if total > MAX_MB << 20:
                raise SystemExit(f"El archivo pasa de {MAX_MB} MB.")
            f.write(parte)
    return ruta, tipo


def detector(umbral, clases, mosaico):
    import numpy as np
    import supervision as sv
    from rfdetr import RFDETRNano
    modelo = RFDETRNano()

    def detectar(img_rgb):
        d = modelo.predict(img_rgb, threshold=umbral)
        return d[np.isin(d.class_id, clases)] if len(d) else d

    if not mosaico:
        return detectar
    slicer = sv.InferenceSlicer(callback=detectar, slice_wh=640, overlap_wh=128, iou_threshold=0.5)
    return lambda img: slicer(img)


def marcar(img_rgb, det, ruta):
    import cv2
    import supervision as sv
    etiquetas = [f"{NOMBRE.get(int(c), c)} {p:.2f}" for c, p in zip(det.class_id, det.confidence)]
    img = sv.BoxAnnotator(thickness=2).annotate(img_rgb.copy(), det)
    img = sv.LabelAnnotator(text_scale=0.4).annotate(img, det, labels=etiquetas)
    alto, ancho = img.shape[:2]
    if ancho > 1600:
        img = cv2.resize(img, (1600, int(alto * 1600 / ancho)))
    cv2.imwrite(ruta, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 82])


def por_especie(det):
    out = {}
    for c in det.class_id:
        n = NOMBRE.get(int(c), str(c))
        out[n] = out.get(n, 0) + 1
    return out


def contar_foto(ruta, detectar, salida_img):
    import cv2
    img = cv2.cvtColor(cv2.imread(ruta), cv2.COLOR_BGR2RGB)
    det = detectar(img)
    marcar(img, det, salida_img)
    conf = float(det.confidence.mean()) if len(det) else 0.0
    return {"tipo": "foto", "ancho_px": img.shape[1], "alto_px": img.shape[0], "total": len(det),
            "por_especie": por_especie(det), "confianza_media": round(conf, 2)}


def seguidor(frame_rate):
    """ByteTrack del paquete trackers de Roboflow (Apache 2.0); en versiones viejas venía dentro de supervision."""
    try:
        from trackers import ByteTrackTracker
        t = ByteTrackTracker(frame_rate=frame_rate, track_activation_threshold=0.5)
        return t.update
    except ImportError:
        import supervision as sv
        return sv.ByteTrack(frame_rate=frame_rate).update_with_detections


def contar_video(ruta, detectar, salida_img):
    import cv2
    cap = cv2.VideoCapture(ruta)
    total_cuadros = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    paso = max(1, total_cuadros // MAX_CUADROS) if total_cuadros else int(fps)
    seguir = seguidor(max(1, round(fps / paso)))
    ids, conteos, confs, mejor = set(), [], [], (-1, None, None)
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % paso == 0:
            ok, cuadro = cap.retrieve()
            if ok:
                rgb = cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)
                det = detectar(rgb)
                conteos.append(len(det))
                confs.extend(float(c) for c in det.confidence)
                seg = seguir(det)
                ids.update(int(t) for t in (seg.tracker_id if seg.tracker_id is not None else []) if t is not None and int(t) >= 0)
                if len(det) > mejor[0]:
                    mejor = (len(det), rgb, det)
            if len(conteos) >= MAX_CUADROS:
                break
        i += 1
    cap.release()
    if mejor[1] is not None:
        marcar(mejor[1], mejor[2], salida_img)
    res = resumen_video(conteos, len(ids))
    res["por_cuadro"] = conteos
    if grafico_video(conteos, salida_img.replace(".jpg", "_grafico.png"), res["distintos_estimados"]):
        res["grafico"] = os.path.basename(salida_img.replace(".jpg", "_grafico.png"))
    conf = sum(confs) / len(confs) if confs else 0.0
    return {"tipo": "video", "duracion_s": round(total_cuadros / fps, 1) if total_cuadros else None,
            **res, "total": res["distintos_estimados"],
            "por_especie": por_especie(mejor[2]) if mejor[2] is not None else {}, "confianza_media": round(conf, 2)}


def grafico_video(conteos, ruta, total):
    """Animales por cuadro a lo largo del video, con el piso (mínimo), el techo (máximo) y la mediana marcados."""
    if not conteos:
        return False
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    lo, hi = min(conteos), max(conteos)
    med = resumen_video(conteos, 0)["mediana_por_cuadro"]
    x = list(range(1, len(conteos) + 1))
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    ax.fill_between(x, lo, hi, color="#d9771a", alpha=.08, label=f"Rango visto: {lo} a {hi}")
    ax.plot(x, conteos, color="#1f4e3d", lw=1.6, label="Animales en el cuadro")
    ax.axhline(hi, color="#c0392b", lw=1, ls="--", label=f"Máximo (techo): {hi}")
    ax.axhline(lo, color="#7a869a", lw=1, ls="--", label=f"Mínimo (piso): {lo}")
    ax.axhline(med, color="#d9771a", lw=1, ls=":", label=f"Mediana: {med:g}")
    ax.set_xlabel("Cuadro revisado")
    ax.set_ylabel("Animales detectados")
    ax.set_ylim(0, max(hi, total) * 1.15 + 1)
    ax.set_title(f"Conteo por cuadro · distintos estimados en todo el video: {total}", fontsize=10, loc="left")
    ax.grid(alpha=.25)
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.text(0.01, 0.01, "DOTS Campo · RF-DETR Nano (Apache 2.0) · conteo de referencia, no inventario", fontsize=6.5, color="#5d665e")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(ruta)
    plt.close(fig)
    return True


def texto_resultado(r):
    rot, expl = lectura_confianza(r["confianza_media"])
    esp = ", ".join(f"{k} {v}" for k, v in r["por_especie"].items()) or "ninguno"
    lin = [f"Conteo de ganado DOTS · {r['generado'][:16].replace('T', ' ')} UTC", f"Archivo: {r['origen']}", ""]
    if r["tipo"] == "foto":
        lin.append(f"Animales detectados en la foto: {r['total']} ({esp}).")
    else:
        lin.append(f"Animales distintos estimados en el video: {r['total']}.")
        lin.append(f"Piso y techo: entre {r['maximo_en_un_cuadro']} (máximo visto en un mismo cuadro, seguro) y "
                   f"{r['total']} (distintos según el seguimiento). Mediana por cuadro: {r['mediana_por_cuadro']} · "
                   f"cuadros revisados: {r['cuadros']}.")
    lin += [f"Confianza media {r['confianza_media']:.2f}".replace(".", ",") + f" ({rot}): {expl}.",
            f"Mosaico (SAHI): {'sí' if r['mosaico'] else 'no'} · umbral {r['umbral']}.",
            "", "Cómo leer la confianza: 0,70 o más alta · 0,50 a 0,70 media · menos de 0,50 baja.",
            "Modelo RF-DETR Nano (Roboflow, Apache 2.0) entrenado con COCO, no con rodeos argentinos:",
            "es un conteo de referencia, no un inventario. Revisar la foto marcada."]
    return "\n".join(lin)


def correo(texto):
    key, dest = os.environ.get("RESEND_API_KEY"), os.environ.get("CONTROL_EMAIL")
    if not key or not dest:
        return "sin configurar"
    import requests
    sender = os.environ.get("AVISOS_FROM") or "DOTS Campo <onboarding@resend.dev>"
    r = requests.post("https://api.resend.com/emails", timeout=30,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"from": sender, "to": [d.strip() for d in dest.split(",") if d.strip()],
                            "subject": "DOTS · Conteo de ganado", "text": texto})
    return "enviado" if r.ok else f"falló: HTTP {r.status_code}"


def main():
    url = (os.environ.get("CONTEO_URL") or "").strip()
    if not url:
        raise SystemExit("Falta el enlace (CONTEO_URL).")
    clases = clases_de(os.environ.get("CONTEO_ESPECIE"))
    mosaico = (os.environ.get("CONTEO_MOSAICO") or "si").strip().lower() not in ("no", "0", "false")
    umbral = float(os.environ.get("CONTEO_UMBRAL") or 0.4)
    os.makedirs(OUT_DIR, exist_ok=True)
    ahora = datetime.now(timezone.utc)
    cid = ahora.strftime("%Y%m%d-%H%M") + "-" + hashlib.sha1(url.encode()).hexdigest()[:6]
    img_out = os.path.join(OUT_DIR, f"{cid}.jpg")
    with tempfile.TemporaryDirectory() as tmp:
        ruta, tipo = descargar(url, tmp)
        detectar = detector(umbral, clases, mosaico)
        r = contar_video(ruta, detectar, img_out) if es_video(ruta, tipo) else contar_foto(ruta, detectar, img_out)
    r.update(id=cid, generado=ahora.isoformat(timespec="seconds"), origen=url, mosaico=mosaico, umbral=umbral,
             especies=[NOMBRE[c] for c in clases], modelo="RF-DETR Nano · COCO · Apache 2.0",
             confianza_lectura=lectura_confianza(r["confianza_media"])[0], imagen=f"{cid}.jpg")
    json.dump(r, open(os.path.join(OUT_DIR, f"{cid}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    texto = texto_resultado(r)
    print(texto)
    print("\nCorreo:", correo(texto))
    return 0


if __name__ == "__main__":
    sys.exit(main())
