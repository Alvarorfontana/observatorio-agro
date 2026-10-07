# DOTS Agentic v0.2

Esta versión agrega una capa operativa de análisis sobre los conectores existentes sin reemplazarlos.

## Interfaz
- Panel **Preguntarle a DOTS**.
- Accesos: Informe integral, Pasturas, Agua, Ganado, Sequía, Suelo y Clima.
- Pregunta libre.
- Resultado con hallazgos, recomendaciones, advertencias, evidencia y confianza operativa.
- PDF inteligente descargable.

## API
- `POST /api/fuentes/agentic`
- `POST /api/fuentes/agentic/pdf`

Cuerpo mínimo: `{"lat": -28.507, "lon": -59.043, "prompt": "Haceme un informe integral"}`.

## Criterio de seguridad de datos
El motor no inventa NDVI, biomasa, animales ni bebederos. Si no existe procesamiento raster o sensor verificable, lo declara como limitación. El puntaje de confianza representa disponibilidad operativa de fuentes y advertencias, no una probabilidad científica.
