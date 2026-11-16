"""Manchas de agua: núcleo matemático para detectar anegamientos con radar Sentinel-1.

Métodos tomados de la astronomía (cómo se separa una galaxia del fondo del cielo) y
llevados a la Tierra. Código propio, solo numpy y scipy, sin red.

  1. Filtro Lee: limpia el «sal y pimienta» del radar (speckle) sin borrar bordes.
  2. Fondo con recorte sigma (sigma clipping): cada píxel tiene su propio «fondo»,
     la mediana de sus pasadas anteriores, con un desvío robusto. Las pasadas raras
     (una inundación vieja, un error) se descartan solas al calcularlo.
  3. Desvío en sigmas (z): cuánto se aparta la última pasada de ese fondo.
     Como una estrella sobre el ruido del cielo, pero al revés: el agua oscurece el radar.
  4. Etiquetado de regiones conectadas: junta los píxeles anómalos en manchas y
     mide superficie, centroide e intensidad de cada una (un «catálogo de fuentes»).
  5. Filtro Hampel: marca fechas raras en una serie temporal sin borrar las demás.

Rangos de lectura (orientativos, sin validar en terreno):
  z medio de la mancha   ≤ −5 fuerte · −5 a −4 moderada · −4 a −3 leve
  Umbral de agua VV      Otsu sobre la escena, aceptado entre −24 y −15 dB; si no, −18 dB fijo.
Límites: no ve agua bajo monte o pajonal denso, no mide profundidad, puede confundir
sombra de radar o suelo muy liso con agua. Píxel mínimo útil: 20 m.
"""
import math
import warnings

import numpy as np
from scipy import ndimage

MAD_A_SIGMA = 1.4826          # convierte la desviación absoluta mediana en un sigma normal
UMBRAL_AGUA_DB = -18.0
Z_UMBRAL = -3.0
SIGMA_PISO_DB = 1.0           # el fondo nunca se considera más estable que 1 dB
# Otsu solo se acepta en el rango habitual del agua abierta en VV; más arriba confunde suelo mojado
OTSU_MIN_DB, OTSU_MAX_DB = -24.0, -15.0


# --------------------------------------------------------------------------- 1. speckle
def filtro_lee(lineal, tam=5, enl=4.4):
    """Filtro Lee multiplicativo sobre retrodispersión lineal. Respeta NaN.

    enl: número equivalente de looks (Sentinel-1 IW GRD ≈ 4,4).
    """
    img = np.asarray(lineal, dtype="float64")
    valido = np.isfinite(img) & (img > 0)
    x = np.where(valido, img, 0.0)
    n = ndimage.uniform_filter(valido.astype("float64"), tam, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        media = ndimage.uniform_filter(x, tam, mode="nearest") / n
        media2 = ndimage.uniform_filter(x * x, tam, mode="nearest") / n
    var = np.maximum(media2 - media * media, 0.0)
    cu2 = 1.0 / enl
    with np.errstate(invalid="ignore", divide="ignore"):
        k = (var - media * media * cu2) / (var * (1.0 + cu2))
    k = np.clip(np.nan_to_num(k, nan=0.0), 0.0, 1.0)
    salida = media + k * (img - media)
    return np.where(valido, salida, np.nan)


def a_db(lineal):
    v = np.asarray(lineal, dtype="float64")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(v) & (v > 0), 10.0 * np.log10(v), np.nan)


# --------------------------------------------------------------------------- 2. fondo
def sigma_recortado(pila, sigma=3.0, iteraciones=5, eje=0):
    """Mediana y sigma robusto a lo largo de `eje`, descartando valores raros.

    Igual que sigma_clipped_stats de astropy: en cada vuelta se sacan los valores a más
    de `sigma` desvíos de la mediana y se recalcula. Devuelve (mediana, sigma, n_usados).
    """
    datos = np.array(pila, dtype="float64", copy=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # píxeles sin ninguna pasada válida
        return _sigma_recortado(datos, sigma, iteraciones, eje)


def _sigma_recortado(datos, sigma, iteraciones, eje):
    for _ in range(iteraciones):
        med = np.nanmedian(datos, axis=eje, keepdims=True)
        mad = np.nanmedian(np.abs(datos - med), axis=eje, keepdims=True)
        sd = MAD_A_SIGMA * mad
        fuera = np.abs(datos - med) > sigma * np.where(sd > 0, sd, np.inf)
        if not np.any(fuera):
            break
        datos[fuera] = np.nan
    med = np.nanmedian(datos, axis=eje)
    sd = MAD_A_SIGMA * np.nanmedian(np.abs(datos - np.expand_dims(med, eje)), axis=eje)
    n = np.sum(np.isfinite(datos), axis=eje)
    return med, sd, n


def desvio_z(actual_db, fondo_med, fondo_sd, piso=SIGMA_PISO_DB):
    """Cuántos sigmas se aparta la pasada actual de su fondo (negativo = más oscuro)."""
    sd = np.maximum(np.nan_to_num(fondo_sd, nan=piso), piso)
    return (np.asarray(actual_db) - fondo_med) / sd


# --------------------------------------------------------------------------- umbral
def umbral_otsu(db, rango=(-35.0, 0.0), bins=128, min_pixeles=500):
    """Umbral agua/tierra por Otsu. Devuelve None si el histograma no sirve."""
    v = np.asarray(db, dtype="float64")
    v = v[np.isfinite(v) & (v >= rango[0]) & (v <= rango[1])]
    if v.size < min_pixeles:
        return None
    cuentas, bordes = np.histogram(v, bins=bins, range=rango)
    p = cuentas / cuentas.sum()
    centros = (bordes[:-1] + bordes[1:]) / 2
    w = np.cumsum(p)
    mu = np.cumsum(p * centros)
    mu_t = mu[-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        entre = (mu_t * w - mu) ** 2 / (w * (1 - w))
    entre = np.nan_to_num(entre)
    i = int(np.argmax(entre))
    t = float(centros[i])
    # sin dos clases representadas (cada lado < 2 %) el umbral no es confiable
    if w[i] < 0.02 or w[i] > 0.98 or not (OTSU_MIN_DB <= t <= OTSU_MAX_DB):
        return None
    return round(t, 2)


# --------------------------------------------------------------------------- 4. manchas
def intensidad(z_medio):
    if z_medio <= -5:
        return "fuerte"
    if z_medio <= -4:
        return "moderada"
    return "leve"


def detectar_manchas(actual_db, fondo_med, fondo_sd, area_pixel_m2, umbral_db=UMBRAL_AGUA_DB,
                     z_umbral=Z_UMBRAL, min_ha=1.0, a_lonlat=None):
    """Catálogo de manchas de agua nueva.

    Un píxel es agua nueva si: hoy está bajo el umbral de agua, su fondo no era agua y
    se oscureció al menos `z_umbral` sigmas. Luego una apertura morfológica 3×3 saca
    píxeles sueltos y se etiquetan regiones con vecindad de 8.
    a_lonlat(fila, col) -> (lon, lat) convierte el centroide a coordenadas.
    """
    actual_db = np.asarray(actual_db, dtype="float64")
    z = desvio_z(actual_db, fondo_med, fondo_sd)
    valido = np.isfinite(actual_db) & np.isfinite(fondo_med)
    agua_hoy = valido & (actual_db < umbral_db)
    agua_fondo = valido & (fondo_med < umbral_db)
    nueva = agua_hoy & ~agua_fondo & (z <= z_umbral)
    nueva = ndimage.binary_opening(nueva, structure=np.ones((3, 3), bool))
    etiquetas, n = ndimage.label(nueva, structure=np.ones((3, 3), int))
    min_px = max(1, int(math.ceil(min_ha * 10000 / area_pixel_m2)))
    manchas = []
    if n:
        idx = np.arange(1, n + 1)
        tam = ndimage.sum(nueva, etiquetas, idx)
        z_med = ndimage.mean(z, etiquetas, idx)
        z_min = ndimage.minimum(z, etiquetas, idx)
        centros = ndimage.center_of_mass(nueva, etiquetas, idx)
        cajas = ndimage.find_objects(etiquetas)
        for i, t, zm, zp, c, caja in zip(idx, tam, z_med, z_min, centros, cajas):
            if t < min_px:
                etiquetas[etiquetas == i] = 0
                continue
            m = {"id": int(i), "pixeles": int(t),
                 "superficie_ha": round(float(t) * area_pixel_m2 / 10000, 2),
                 "z_medio": round(float(zm), 2), "z_pico": round(float(zp), 2),
                 "intensidad": intensidad(float(zm)),
                 "fila_col": [round(float(c[0]), 1), round(float(c[1]), 1)],
                 "caja": [caja[0].start, caja[1].start, caja[0].stop, caja[1].stop]}
            if a_lonlat:
                lon, lat = a_lonlat(float(c[0]), float(c[1]))
                m["centroide"] = [round(lon, 5), round(lat, 5)]
            manchas.append(m)
    manchas.sort(key=lambda m: -m["superficie_ha"])
    resumen = {
        "pixeles_validos": int(valido.sum()),
        "agua_hoy_ha": round(float(agua_hoy.sum()) * area_pixel_m2 / 10000, 1),
        "agua_habitual_ha": round(float(agua_fondo.sum()) * area_pixel_m2 / 10000, 1),
        "agua_nueva_ha": round(sum(m["superficie_ha"] for m in manchas), 1),
        "manchas": len(manchas),
    }
    return manchas, etiquetas, resumen


# --------------------------------------------------------------------------- 5. series
def hampel(serie, ventana=3, t=3.0):
    """Marca valores raros de una serie (True = raro). No modifica la serie.

    Cada punto se compara con la mediana de sus `ventana` vecinos a cada lado.
    Sirve para avisar «esta fecha no se parece a las de alrededor» (nube no detectada,
    error de sensor… o un evento real que hay que mirar).
    """
    x = np.asarray(serie, dtype="float64")
    raro = np.zeros(x.size, dtype=bool)
    for i in range(x.size):
        lo, hi = max(0, i - ventana), min(x.size, i + ventana + 1)
        vec = x[lo:hi]
        vec = vec[np.isfinite(vec)]
        if vec.size < 3 or not np.isfinite(x[i]):
            continue
        med = np.median(vec)
        sd = MAD_A_SIGMA * np.median(np.abs(vec - med))
        if sd > 0 and abs(x[i] - med) > t * sd:
            raro[i] = True
    return raro
