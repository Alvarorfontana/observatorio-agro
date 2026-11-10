# DOTS · trabajador GPU de visión bovina

## Arquitectura

El navegador carga el video directamente a un bucket privado Cloudflare R2 mediante una URL prefirmada de 15 minutos. Flask (`vision_api.py`) crea un trabajo en RunPod Serverless. El worker descarga el MP4 desde R2, ejecuta YOLO26n (clase COCO `cow`) y BoT-SORT en GPU, y devuelve conteos por fotograma y tracks temporales.

## Despliegue externo

1. Crear un bucket privado en Cloudflare R2 y generar credenciales de objeto con permisos mínimos de lectura/escritura sobre `vision/uploads/*`.
2. Crear un endpoint RunPod Serverless a partir de este Dockerfile; seleccionar una GPU compatible y configurar el handler `handler.py`.
3. Configurar en RunPod: `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`. No guardar secretos en Git.
4. Configurar en Vercel: `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`.
5. Re-deploy de Vercel y consultar `GET /api/fuentes/vision/status`. El estado debe ser `ready`.

## Límites de esta primera versión

- Video MP4/MOV/M4V, hasta 100 MB y 120 segundos. El worker procesa hasta 240 fotogramas muestreados.
- Detección de la clase bovina `cow` del conjunto COCO. No es un modelo entrenado específicamente con rodeos argentinos ni discrimina raza, sexo o caravana.
- BoT-SORT produce IDs temporales de seguimiento, no identidad individual permanente.
- La prueba de precisión requiere un conjunto de videos de campo anotados y una evaluación independiente (precision, recall, mAP, IDF1/HOTA).
- El bucket debe tener CORS para permitir `PUT` desde el dominio DOTS y aceptar `Content-Type: video/mp4`.
- Los videos se conservan en R2 hasta que se configure una política de borrado/retención; el primer despliegue debe definirla antes de usar videos sensibles.

El procesamiento GPU es externo a Vercel y al equipo del usuario. Sin las credenciales R2/RunPod, el endpoint informa `configuration_required` y no simula resultados.
