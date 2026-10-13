"""pngmini — leer y escribir PNG de 8 bits en Python puro (zlib). Reemplaza a Pillow para que la función de Vercel
no crezca: alcanza para medir nubes, medir la máscara de GFM y recolorearla."""
import struct, zlib

SIG = b'\x89PNG\r\n\x1a\n'


def size(data):
    """(ancho, alto) de un PNG o JPEG sin decodificarlo. None si no se reconoce."""
    if data[:8] == SIG:
        return struct.unpack('>II', data[16:24])
    if data[:3] == b'\xff\xd8\xff':
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1; continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack('>HH', data[i + 5:i + 9]); return w, h
            i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
    return None


def decode(data):
    """PNG de 8 bits (gris, RGB, paleta, gris+alfa, RGBA; sin entrelazado) → (ancho, alto, filas de tuplas RGBA)."""
    if data[:8] != SIG:
        raise ValueError('No es PNG')
    pos, idat, plte, trns = 8, [], None, None
    w = h = depth = ctype = inter = None
    while pos < len(data):
        n, typ = struct.unpack('>I4s', data[pos:pos + 8]); body = data[pos + 8:pos + 8 + n]; pos += 12 + n
        if typ == b'IHDR':
            w, h, depth, ctype, _, _, inter = struct.unpack('>IIBBBBB', body)
        elif typ == b'PLTE':
            plte = [tuple(body[k:k + 3]) for k in range(0, len(body), 3)]
        elif typ == b'tRNS':
            trns = body
        elif typ == b'IDAT':
            idat.append(body)
        elif typ == b'IEND':
            break
    if depth != 8 or inter:
        raise ValueError('PNG no soportado')
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b''.join(idat))
    stride = w * bpp
    prev = bytearray(stride); rows = []; i = 0
    for _ in range(h):
        f = raw[i]; line = bytearray(raw[i + 1:i + 1 + stride]); i += 1 + stride
        if f == 1:
            for x in range(bpp, stride): line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            for x in range(stride): line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride): line[x] = (line[x] + ((line[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0; b = prev[x]; c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        if ctype == 6:
            px = [tuple(line[k:k + 4]) for k in range(0, stride, 4)]
        elif ctype == 2:
            key = struct.unpack('>HHH', trns) if trns and len(trns) == 6 else None
            px = [(r, g, b, 0 if key and (r, g, b) == key else 255) for r, g, b in (line[k:k + 3] for k in range(0, stride, 3))]
        elif ctype == 3:
            px = [plte[v] + ((trns[v] if trns and v < len(trns) else 255),) for v in line]
        elif ctype == 4:
            px = [(line[k], line[k], line[k], line[k + 1]) for k in range(0, stride, 2)]
        else:
            key = struct.unpack('>H', trns)[0] if trns and len(trns) == 2 else None
            px = [(v, v, v, 0 if v == key else 255) for v in line]
        rows.append(px)
    return w, h, rows


def encode_rgba(w, h, rows):
    raw = b''.join(b'\x00' + bytes(v for p in row for v in p) for row in rows)
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xFFFFFFFF)
    return SIG + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
