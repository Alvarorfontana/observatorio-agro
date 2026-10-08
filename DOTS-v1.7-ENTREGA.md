# DOTS Campo v1.7 — cierre funcional del núcleo

Correcciones principales: geometría del lote enviada a consultas compatibles; Sentinel-2 busca por bbox del lote; FIRMS usa bbox del lote con margen y clasifica detecciones dentro/entorno; marcadores incorporan procedencia/confianza/fecha; estado manual persistente; barra principal elimina botones que aparentaban ser imágenes cuando eran sólo catálogos; PDF incorpora imagen NASA GIBS cuando responde y superpone polígono + marcas; script de auditoría por fuente.

La capa NASA GIBS/MODIS es una capa visual. Sentinel-2 permanece explícitamente como catálogo hasta contar con procesamiento raster. Las fuentes protegidas permanecen deshabilitadas conceptualmente hasta una prueba autenticada end-to-end.

Validación local: los módulos Python compilan. El build frontend no pudo certificarse en este entorno porque `npm ci` no completó la instalación de dependencias antes del timeout; no se afirma build exitoso.
