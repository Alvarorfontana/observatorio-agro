#!/usr/bin/env python3
"""Import only reviewed Python source files from the user-provided ENSO ZIP.

No binaries, caches, generated reports, synthetic datasets or dashboards are copied.
Run locally from the repository root; inspect git diff before committing.
"""
from __future__ import annotations
import pathlib
import sys
import zipfile

PREFIX = "clima-enso-pack/repo/clima-enso-analyzer/"
DEST = pathlib.Path("integrations/clima-enso-analyzer")
ALLOWED = {".py", ".toml", ".md", ".txt"}
MAX_FILE = 512_000
MAX_TOTAL = 8_000_000

def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python3 tools/import_clima_enso_pack.py <clima-enso-pack-v4.zip>")
        return 2
    archive = pathlib.Path(sys.argv[1])
    if not archive.is_file():
        print(f"No existe: {archive}")
        return 2
    total = 0
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"Archivo ZIP dañado: {bad}")
        files = []
        for item in z.infolist():
            if item.is_dir() or not item.filename.startswith(PREFIX):
                continue
            relative = pathlib.PurePosixPath(item.filename[len(PREFIX):])
            if (not relative.parts or ".." in relative.parts
                    or relative.is_absolute() or relative.suffix.lower() not in ALLOWED):
                continue
            if item.file_size > MAX_FILE:
                raise ValueError(f"Archivo demasiado grande: {relative}")
            total += item.file_size
            if total > MAX_TOTAL:
                raise ValueError("Límite de importación excedido")
            files.append((item, relative))
        if not files:
            raise ValueError("No se encontró el proyecto Python esperado")
        for item, relative in files:
            target = DEST.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
            print(f"Importado: {target}")
    print(f"Listo: {len(files)} archivos de código y documentación; revisar licencia y dependencias.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
