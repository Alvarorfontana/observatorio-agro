# DOTS v3.0 · Conteo de ganado gratis (RF-DETR + mosaico SAHI)

Retoma la visión ganadera que quedó en pausa porque dependía de RunPod (GPU paga) y Cloudflare R2. Ahora corre en
una máquina común de GitHub Actions, gratis, y no toca el sitio: no hay IA dentro de la web.

## Cómo se usa

Actions → **Conteo de ganado** → Run workflow:

| Campo | Qué poner |
|---|---|
| url | enlace directo a la foto o el video. De Google Drive sirve el enlace de compartir («cualquier persona con el enlace») |
| especie | vaca, oveja, caballo o todas |
| mosaico | **si** para drone o animales lejos; **no** para fotos de celular de cerca |
| umbral | confianza mínima, 0,4 por defecto |

El resultado aparece en el resumen de la tarea, llega por correo si están `RESEND_API_KEY` y `CONTROL_EMAIL`, y queda
en la rama `datos` (`data/conteo_ganado/<id>.json` y la foto marcada `<id>.jpg`).

## Cómo cuenta

- **Modelo**: RF-DETR Nano de Roboflow, preentrenado con COCO (clases vaca, oveja, caballo). Licencia Apache 2.0:
  libre también para uso comercial, a diferencia de YOLO26 y YOLO11 (AGPL), que usaba el trabajador de RunPod.
- **Mosaico (SAHI)**: la imagen se corta en cuadros de 640 px que se pisan 128 px, se detecta en cada uno y se juntan
  los resultados quitando duplicados. Es lo que hace aparecer los animales chicos de una foto de drone.
- **Video**: hasta 90 cuadros repartidos en todo el video. Por cuadro se cuenta; entre cuadros se siguen los animales
  con ByteTrack (paquete `trackers` de Roboflow, Apache 2.0) para estimar cuántos distintos pasaron.

## Cómo leerlo

| Dato | Qué significa |
|---|---|
| Animales en la foto | detecciones en toda la imagen |
| Distintos estimados (video) | animales seguidos entre cuadros; nunca menos que el máximo visto en un cuadro |
| Máximo en un cuadro | piso seguro: al menos esa cantidad había |
| Confianza 0,70 o más | alta: el modelo reconoce bien a los animales |
| Confianza 0,50 a 0,70 | media: revisar la foto marcada |
| Confianza menos de 0,50 | baja: imagen difícil, número orientativo |

## Límites

- No está entrenado con rodeos argentinos: es un conteo de referencia, no un inventario. Animales muy juntos, de
  noche o tapados por árboles se pierden o se cuentan doble. Para producción hace falta un set de videos de campo
  anotados y medir precisión (precision, recall, mAP; IDF1 para el seguimiento).
- Sin GPU: una foto tarda segundos; un video de 2 minutos, unos minutos. Archivos de hasta 200 MB.
- El seguimiento da identidades temporales, no reconoce a un animal de un día para otro.
- Los satélites gratuitos (Sentinel, 10 m) no ven animales: hace falta drone, cámara o celular.

## Próximo paso posible

Afinar RF-DETR con fotos propias de rodeos (se entrena gratis en Colab) y sumar la reidentificación del paquete
`trackers` para no contar dos veces al mismo animal cuando sale y vuelve a entrar en cuadro.

## Archivos

- `scripts/conteo_ganado.py` · descarga, detección, mosaico, seguimiento, correo
- `.github/workflows/conteo-ganado.yml` · tarea a pedido
- `tests/test_conteo_ganado.py` · pruebas sin descargar el modelo
