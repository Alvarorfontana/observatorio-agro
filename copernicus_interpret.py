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
    "ndvi_change": {
        "name": "Cambio de NDVI entre dos períodos",
        "about": "Resta el NDVI del período de comparación al del período actual, píxel por píxel y solo donde las dos fechas están despejadas. Rojo es pérdida de vegetación; verde, ganancia.",
        "cuts": [-0.2, -0.05, 0.05, 0.2],
        "classes": [
            ((178, 24, 43), "menor a -0,2", "Pérdida fuerte de vegetación"),
            ((239, 138, 98), "-0,2 a -0,05", "Pérdida leve de vegetación"),
            ((237, 237, 226), "-0,05 a 0,05", "Sin cambio importante"),
            ((127, 188, 65), "0,05 a 0,2", "Ganancia leve de vegetación"),
            ((33, 120, 47), "mayor a 0,2", "Ganancia fuerte de vegetación"),
        ],
    },
    "s1_water": {
        "name": "Agua por radar · Sentinel-1",
        "about": "El radar mide cuánta señal rebota en el terreno y funciona con nubes y de noche. El agua quieta refleja la señal lejos del satélite y aparece muy oscura (valores bajos en dB).",
        "cuts": [-20, -18, -15],
        "classes": [
            ((26, 96, 180), "menor a -20 dB", "Agua abierta"),
            ((98, 177, 209), "-20 a -18 dB", "Agua probable o superficie muy lisa"),
            ((197, 212, 172), "-18 a -15 dB", "Suelo muy húmedo o vegetación baja"),
            ((171, 139, 92), "mayor a -15 dB", "Sin agua: suelo o vegetación"),
        ],
    },
    "lst": {
        "name": "Temperatura superficial · Sentinel-3",
        "about": "Es la temperatura de la superficie del suelo y la vegetación medida desde el satélite en la pasada de la mañana (alrededor de las 10). No es la temperatura del aire: al sol puede superarla varios grados.",
        "cuts": [15, 25, 35, 45],
        "classes": [
            ((69, 117, 180), "menor a 15 °C", "Fresco"),
            ((145, 191, 219), "15 a 25 °C", "Templado"),
            ((254, 224, 144), "25 a 35 °C", "Cálido"),
            ((244, 109, 67), "35 a 45 °C", "Muy caliente: posible estrés térmico"),
            ((165, 0, 38), "mayor a 45 °C", "Extremo: estrés térmico severo"),
        ],
    },
    "co": {
        "name": "Monóxido de carbono · Sentinel-5P",
        "about": "Columna total de monóxido de carbono en la atmósfera. En la región, los aumentos suelen venir del humo de quemas e incendios, muchas veces transportado desde lejos.",
        "cuts": [0.03, 0.04, 0.06],
        "classes": [
            ((255, 255, 204), "menor a 0,03 mol/m²", "Nivel de fondo"),
            ((254, 217, 118), "0,03 a 0,04 mol/m²", "Levemente elevado"),
            ((253, 141, 60), "0,04 a 0,06 mol/m²", "Alto: posible humo de quemas"),
            ((189, 0, 38), "mayor a 0,06 mol/m²", "Muy alto: humo denso"),
        ],
    },
    "no2": {
        "name": "Dióxido de nitrógeno · Sentinel-5P",
        "about": "Columna troposférica de NO₂. Sale de motores, industrias, centrales y quemas; en zonas rurales suele ser bajo.",
        "cuts": [0.00002, 0.00005, 0.0001],
        "classes": [
            ((255, 255, 204), "menor a 20 µmol/m²", "Bajo: aire rural limpio"),
            ((254, 217, 118), "20 a 50 µmol/m²", "Moderado"),
            ((253, 141, 60), "50 a 100 µmol/m²", "Alto: ciudades, rutas, industria o quemas"),
            ((189, 0, 38), "mayor a 100 µmol/m²", "Muy alto"),
        ],
    },
    "aerosol": {
        "name": "Aerosoles y humo · Sentinel-5P",
        "about": "Índice de aerosoles UV: valores positivos indican partículas que absorben luz, como humo o polvo. Detecta humo incluso sobre nubes.",
        "cuts": [0, 1, 2],
        "classes": [
            ((224, 236, 244), "menor a 0", "Sin aerosoles absorbentes"),
            ((254, 217, 118), "0 a 1", "Bajo"),
            ((253, 141, 60), "1 a 2", "Moderado: humo o polvo"),
            ((189, 0, 38), "mayor a 2", "Alto: humo denso"),
        ],
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
    extra = stats.get("extra") or {}
    if not stats.get("valid_pixels"):
        return lines + ["No hubo píxeles válidos en el período elegido (nubes o sin pasadas). Probá ampliar las fechas."]
    regional = index in ("lst", "co", "no2", "aerosol")
    top = max(stats["classes"], key=lambda c: c["pct"])
    where = f"en la zona de unos {extra.get('region_km', '')} km alrededor del lote" if regional else "del área"
    lines.append(f"La clase dominante es «{top['label'].lower()}» ({top['range']}), con el {top['pct']:.0f}% {where}.")
    if regional:
        parcel = extra.get("parcel")
        if parcel:
            lines.append(f"Sobre el lote (marcado en blanco) el valor cae en «{parcel['label'].lower()}» ({parcel['range']}).")
        elif "parcel" in extra:
            lines.append("Sobre el lote no hubo dato válido en el período (nubes o sin cobertura).")
    if index == "ndvi_change":
        loss, gain = _p(stats, 0, 1), _p(stats, 3, 4)
        if extra.get("before") and extra.get("after"):
            lines.append(f"Compara {extra['before']} contra {extra['after']}.")
        if "mean_before" in extra:
            lines.append("El NDVI medio del lote pasó de %s a %s." % (f"{extra['mean_before']:.2f}".replace(".", ","), f"{extra['mean_after']:.2f}".replace(".", ",")))
        if loss >= 20:
            lines.append(f"El {loss:.0f}% del lote perdió vegetación. Puede ser cosecha, pastoreo intenso, sequía, quema o anegamiento: conviene cruzarlo con lo que se hizo en el lote.")
        if gain >= 20:
            lines.append(f"El {gain:.0f}% ganó vegetación: siembra que emergió, rebrote de pasturas o recuperación después de lluvias.")
        if loss < 20 and gain < 20:
            lines.append("El lote se mantuvo estable entre los dos períodos.")
    elif index == "s1_water":
        water, wet = _p(stats, 0, 1), _p(stats, 2)
        if extra.get("acquired"):
            lines.append(f"Imagen de radar del {extra['acquired']}.")
        lines.append(f"Se detecta agua o superficie anegada en el {water:.0f}% del lote." if water >= 1 else "No se detecta agua abierta en el lote.")
        if wet >= 10:
            lines.append(f"Otro {wet:.0f}% muestra suelo muy húmedo: zona a vigilar si sigue lloviendo o sube el río.")
        lines.append("Ojo: el monte o el pastizal alto inundado pueden verse brillantes y no como agua; y caminos, arena o suelo muy liso pueden verse oscuros sin ser agua. Contrastalo con el NDWI y las alturas del INA.")
    elif index == "lst":
        hot = _p(stats, 3, 4)
        if hot >= 10:
            lines.append(f"El {hot:.0f}% de la zona superó los 35 °C en superficie: condiciones de estrés térmico para cultivos y hacienda. Revisá agua y sombra.")
        lines.append("Cada píxel mide 1 km: muestra el patrón de la zona, no diferencias dentro de un lote chico.")
    elif index in ("co", "no2", "aerosol"):
        high = _p(stats, 2, 3)
        if high >= 5:
            cause = ("Suele venir de ciudades, rutas e industrias; si coincide con focos de calor, también de quemas."
                     if index == "no2" else
                     "Si coincide con focos de calor, es humo de quemas: puede afectar la visibilidad en rutas y la salud respiratoria.")
            lines.append(f"El {high:.0f}% de la zona muestra valores altos. {cause}")
        else:
            lines.append("La zona no muestra valores altos en el período.")
        lines.append("Es un dato regional de unos 5 km por píxel promediado en el período: describe el aire de la zona y no atribuye emisiones al lote.")
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
    elif index == "ndwi":
        water, wet = _p(stats, 2, 3), _p(stats, 1)
        if water >= 1:
            lines.append(f"Se detecta agua en superficie en el {water:.0f}% del área.")
        else:
            lines.append("No se detecta agua abierta dentro del lote.")
        if wet >= 5:
            lines.append(f"Otro {wet:.0f}% muestra suelo muy húmedo o encharcamiento: puede anticipar anegamiento si siguen las lluvias o sube el río.")
        lines.append("Para confirmar una inundación bajo nubes, contrastá con radar Sentinel-1 y con las alturas del INA.")
    if index in ("ndvi", "ndwi", "ndvi_change"):
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
