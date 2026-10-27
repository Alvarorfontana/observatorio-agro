#!/usr/bin/env bash
# Guarda y recupera los datos de las tareas automáticas en la rama `datos` (no se publica en Vercel).
#   scripts/datos_rama.sh traer            → copia data/ y scripts/cache/ de la rama `datos` al directorio de trabajo
#   scripts/datos_rama.sh guardar "msg" f… → sube los archivos indicados a la rama `datos`
set -u
cmd="$1"; shift
if [ "$cmd" = "traer" ]; then
  git fetch -q origin datos 2>/dev/null && git checkout -q origin/datos -- data 2>/dev/null || true
  git checkout -q origin/datos -- scripts/cache 2>/dev/null || true
  git reset -q 2>/dev/null || true
  exit 0
fi
msg="$1"; shift
tmp=$(mktemp -d)
for f in "$@"; do [ -e "$f" ] && mkdir -p "$tmp/$(dirname "$f")" && cp -r "$f" "$tmp/$f"; done
git config user.name "DOTS datos"; git config user.email "actions@users.noreply.github.com"
git stash -q -u 2>/dev/null || true
if git fetch -q origin datos 2>/dev/null; then git checkout -q -B datos origin/datos; else git checkout -q --orphan datos && git rm -rqf --cached . >/dev/null; fi
cp -r "$tmp"/. .
echo '{"git":{"deploymentEnabled":false}}' > vercel.json
# Se agrega uno por uno: si falta un archivo (por ejemplo, una carpeta de fotos vacía), git no descarta el resto
git add vercel.json
for f in "$@"; do [ -e "$f" ] && git add -- "$f"; done
if git diff --cached --quiet; then echo "Sin cambios."; exit 0; fi
git commit -q -m "$msg"
for i in 1 2 3; do git push -q origin datos && exit 0; git pull -q --rebase origin datos || true; done
exit 1
