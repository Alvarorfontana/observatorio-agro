# DOTS / Campo · reglas del proyecto

Observatorio agroclimático y satelital. Repo público `Alvarorfontana/observatorio-agro`, desplegado en Vercel.
Valen para cualquier persona o IA que trabaje acá. Antes de empezar, leer también `PROGRESO.md`.

## Reglas de oro
1. **Nada de APIs de Claude ni de IA dentro del sitio.** Los cálculos con modelos corren afuera (GitHub Actions).
2. Solo herramientas y servicios gratuitos. Earth Engine con la cuota no comercial común.
3. **Cada módulo muestra sus rangos de lectura y sus límites** (piso, techo, qué no puede ver), con gráficos.
4. Textos para todo público: productores, estudiantes, profesionales, periodistas, divulgadores.
5. Diseño estático y serio, pocas animaciones.
6. Mensajes de crecidas: formales, sin emojis. Avisos por correo antes que por Telegram.
7. No inventar datos: indicar fuente, fecha, sensor y si es medición o modelo.
8. Modo vitrina: el sitio se ve, pero usarlo (consultas, informes) pide clave de invitación.
9. Ninguna clave en el código ni en los commits (repo público): usar secretos de GitHub o Vercel.
10. Lo que no está validado en el terreno se marca como «orientativo».

## Después de cada cambio
1. Build sin errores y pruebas (`pytest`) de lo que se tocó.
2. Probar con y sin clave, y en el celular.
3. Si se suma una fuente: documentar resolución, frecuencia, licencia y cita (`THIRD-PARTY-NOTICES.md`).
4. Anotar el cambio en `PROGRESO.md` (fecha, qué se hizo, qué quedó pendiente).
