"""Lectura de mapas temáticos y gráficos de escenas Copernicus.

Reglas fijas y verificables (sin IA): cuenta los píxeles de cada clase del mapa
que devuelve Sentinel Hub y arma la interpretación con rangos de lectura.
"""
from collections import Counter

import pngmini

# Cada clase: color exacto que pinta el evalscript, rango del índice, nombre y lectura.
MAP_CLASSES = {
    "ndvi": {
        "name": "NDVI · vigor vegetal",
        "about": "El NDVI compara la luz roja que la planta absorbe con el infrarrojo cercano que refleja. Va de -1 a 1: cuanto más alto, más biomasa verde y activa.",
        "classes": [
            ((145, 95, 65), "menor a 0", "Agua, suelo desnudo o sin vegetación"),
            ((230, 188, 90), "0 a 0,2", "Vegetación muy escasa, rastrojo o suelo expuesto"),
            ((203, 223, 83), "0,2 a 0,45", "Vegetación moderada o pastizal en reposo"),
            ((86, 171, 77), "0,45 a 0,7", "Vegetación vigorosa"),
            ((16, 106, 54), "mayor a 0,7", "Vegetación muy densa, monte o cultivo en pleno desarrollo"),
        ],
    },
    "ndwi": {
        "name": "NDWI · índice de agua",
        "about": "El NDWI compara la luz verde con el infrarrojo cercano. Los valores positivos indican agua en superficie; los negativos, suelo o vegetación.",
        "classes": [
            ((171, 139, 92), "menor a 0", "Sin agua superficial: suelo o vegetación"),
            ((197, 212, 172), "0 a 0,2", "Suelo muy húmedo, encharcamiento o borde de agua"),
            ((98, 177, 209), "0,2 a 0,4", "Agua probable, poco profunda o con sedimentos"),
            ((26, 96, 180), "mayor a 0,4", "Agua abierta"),
        ],
    },
    "truecolor": {
        "name": "Color natural",
        "about": "Composición de las bandas roja, verde y azul, como la vería el ojo humano. No es un índice: sirve para reconocer el terreno y verificar los otros mapas.",
        "classes": [],
    },
}

CAVEAT = ("La imagen es un mosaico del período elegido que prioriza la menor nubosidad. "
          "Nubes o sombras residuales pueden aparecer como valores bajos. "
          "Es una lectura satelital orientativa a 10 m de resolución y conviene verificarla en el campo.")


def _nearest(rgb, palette):
    best, dist = None, None
    for i, c in enumerate(palette):
        d = sum((a - b) ** 2 for a, b in zip(rgb, c))
        if dist is None or d < dist:
            best, dist = i, d
    return best if dist is not None and dist <= 300 else None


def map_stats(png, index):
    """Porcentaje del lote en cada clase, contando solo píxeles dentro del polígono."""
    spec = MAP_CLASSES.get(index)
    if not spec or not spec["classes"]:
        return {"index": index, "valid_pixels": None, "classes": []}
    _, _, rows = pngmini.decode(png)
    palette = [c[0] for c in spec["classes"]]
    counts, valid = Counter(), 0
    for row in rows:
        for r, g, b, a in row:
            if a == 0:
                continue
            k = _nearest((r, g, b), palette)
            if k is not None:
                counts[k] += 1
                valid += 1
    out = []
    for i, (rgb, rng, label) in enumerate(spec["classes"]):
        pct = round(100 * counts[i] / valid, 1) if valid else 0.0
        out.append({"range": rng, "label": label, "color": "#%02x%02x%02x" % rgb, "pct": pct})
    return {"index": index, "valid_pixels": valid, "classes": out}


def _p(stats, *idx):
    return sum(stats["classes"][i]["pct"] for i in idx)


def interpret_map(index, stats):
    """Frases de lectura del mapa, en lenguaje llano."""
    spec = MAP_CLASSES.get(index, {})
    lines = [spec.get("about", "")]
    if index == "truecolor" or not stats.get("classes"):
        lines.append("Usalo para identificar lagunas, caminos, monte y lotes, y para comprobar que el NDVI o el NDWI no estén afectados por nubes.")
        lines.append(CAVEAT)
        return [l for l in lines if l]
    if not stats.get("valid_pixels"):
        return lines + ["No hubo píxeles válidos dentro del lote en el período elegido. Probá ampliar las fechas."]
    top = max(stats["classes"], key=lambda c: c["pct"])
    lines.append(f"La clase dominante es «{top['label'].lower()}» ({top['range']}), con el {top['pct']:.0f}% del área.")
    if index == "ndvi":
        bare, vigor = _p(stats, 0, 1), _p(stats, 3, 4)
        if vigor >= 60:
            lines.append(f"El {vigor:.0f}% del lote muestra vegetación vigorosa o densa: buena cobertura y actividad fotosintética.")
        elif vigor >= 30:
            lines.append(f"El {vigor:.0f}% muestra vegetación vigorosa. Hay sectores con menos cobertura que conviene recorrer.")
        else:
            lines.append(f"Solo el {vigor:.0f}% muestra vegetación vigorosa. Puede deberse a la época del año, a un lote recién cosechado o sembrado, o a estrés hídrico.")
        if bare >= 20:
            lines.append(f"El {bare:.0f}% aparece como suelo desnudo, agua o vegetación muy escasa. Si el lote debería estar cubierto, son los sectores a inspeccionar primero.")
    else:
        water, wet = _p(stats, 2, 3), _p(stats, 1)
        if water >= 1:
            lines.append(f"Se detecta agua en superficie en el {water:.0f}% del área.")
        else:
            lines.append("No se detecta agua abierta dentro del lote.")
        if wet >= 5:
            lines.append(f"Otro {wet:.0f}% muestra suelo muy húmedo o encharcamiento: puede anticipar anegamiento si siguen las lluvias o sube el río.")
        lines.append("Para confirmar una inundación bajo nubes, contrastá con radar Sentinel-1 y con las alturas del INA.")
    lines.append(CAVEAT)
    return [l for l in lines if l]


def interpret_scenes(scenes):
    """Lectura de los gráficos de escenas (fechas y nubosidad)."""
    dates, clouds = set(), []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        p = s.get("properties") or {}
        d = str(p.get("datetime") or "")[:10]
        if len(d) == 10:
            dates.add(d)
        c = p.get("eo:cloud_cover")
        if isinstance(c, (int, float)) and 0 <= c <= 100:
            clouds.append(c)
    if not scenes:
        return ["No hay escenas en el período: no se puede evaluar la frecuencia de observación."]
    lines = [f"Se encontraron {len(scenes)} escenas en {len(dates)} fechas distintas."]
    if len(dates) >= 2:
        ds = sorted(dates)
        from datetime import date
        span = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days
        lines.append(f"En promedio hay una pasada cada {span / (len(ds) - 1):.0f} días, lo que alcanza para seguir cambios semanales del lote.")
    if clouds:
        clear = sum(1 for c in clouds if c < 20)
        lines.append(f"{clear} de {len(clouds)} escenas tienen menos de 20% de nubes y son las más confiables para medir índices.")
        if clear == 0:
            lines.append("Ninguna escena está despejada: los índices ópticos pueden estar afectados. Para agua conviene usar radar Sentinel-1, que atraviesa las nubes.")
    else:
        lines.append("Esta colección no informa nubosidad (por ejemplo radar o productos atmosféricos).")
    return lines
