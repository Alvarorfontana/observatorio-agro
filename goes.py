"""goes v1.0 — utilidades para los productos del satélite GOES-19 (NOAA, datos abiertos en AWS, sin clave).

Rayos: GLM (Geostationary Lightning Mapper), archivos cada 20 segundos con cada destello detectado (latitud, longitud,
energía). Heladas: temperatura de la superficie terrestre del ABI (producto LSTF, disco completo, cada hora, ~10 km
en el nadir), sólo con cielo despejado. Se procesan en GitHub Actions; la web lee el resultado.
"""
import math

BUCKET = 'https://noaa-goes19.s3.amazonaws.com'


def latlon_to_xy(lat, lon, lon0, H, a, b):
    """Ángulos de barrido (x, y, en radianes) de la grilla fija del ABI para un punto; None si no lo ve el satélite.
    Fórmulas de la Guía de Usuario de GOES-R (PUG, vol. 3, 4.2.8.2). H = altura del satélite + semieje mayor."""
    phi, lam = math.radians(lat), math.radians(lon)
    e2 = (a * a - b * b) / (a * a)
    phic = math.atan((b * b) / (a * a) * math.tan(phi))
    rc = b / math.sqrt(1 - e2 * math.cos(phic) ** 2)
    sx = H - rc * math.cos(phic) * math.cos(lam - math.radians(lon0))
    sy = -rc * math.cos(phic) * math.sin(lam - math.radians(lon0))
    sz = rc * math.sin(phic)
    if H * (H - sx) < sy * sy + (a * a) / (b * b) * sz * sz:
        return None
    x = math.asin(-sy / math.sqrt(sx * sx + sy * sy + sz * sz))
    y = math.atan(sz / sx)
    return x, y


def index_of(v, v0, dv, n):
    i = int(round((v - v0) / dv))
    return i if 0 <= i < n else None


def grid_cells(bbox, step):
    w, s, e, n = bbox
    out = []
    lat = s + step / 2
    while lat < n:
        lon = w + step / 2
        while lon < e:
            out.append((round(lat, 3), round(lon, 3)))
            lon += step
        lat += step
    return out


def km(a, b):
    r = math.pi / 180
    h = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))
