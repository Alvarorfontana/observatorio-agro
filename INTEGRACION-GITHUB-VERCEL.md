# Integración React + GIS + APIs en observatorio-agro

Repositorio existente: https://github.com/Alvarorfontana/observatorio-agro
Base de esta copia: 4d421f97d1317797ae48d83900f23acaa7a60ed4. Los cambios se prepararon localmente; no se publicaron ni hicieron push.

## Qué se integró

React 19 + TypeScript + Vite, Leaflet, ECharts, iconos vectoriales. Mapa satelital completo, panel izquierdo denso, gráficos, fotografía Sentinel-2 real de escena, herramientas de delimitación, historial de 20/30 años y exportación JSON/PDF multifuente (clima, aire y relieve; INA si está seleccionado). Python/Flask sigue siendo el backend. Selector INA incluye altura reciente, altura mensual de 30 años y temperatura observada; USGS permite elegir una estación explícita. La página original se conserva en templates/index.html y en /legacy; el módulo principal es React en /. APIs nuevas usan /api/fuentes/* para evitar mezclar el formato del prototipo con el formato antiguo.

La imagen Preview es captura del frontend compilado y servido por Flask. Ese mismo frontend se genera para Vercel. El mapa/fotos, fechas y cifras cambian con la consulta; la captura no es promesa de valores permanentes. El resultado exacto depende del tamaño de pantalla y acceso a servicios externos.

## Probar localmente

Node 22.12+ y Python 3.12. Desde la raíz:

```bash
npm ci
npm run build
python -m venv .venv
```

Activar el entorno (Windows: `.venv\Scripts\activate`; macOS/Linux: `source .venv/bin/activate`). Después:

```bash
pip install -r requirements.txt
flask --app api.index run --port 8000
```

Abrir http://127.0.0.1:8000. Para editar frontend ejecutar `npm run dev` en otra terminal; Vite redirige /api al backend 8000. No abrir index.html haciendo doble clic.

## Subir al mismo GitHub y Vercel

1. Crear una rama `integracion-gis-investigacion` en el repo existente. Descomprimir el ZIP y copiar su contenido a la raíz de esa rama, respetando las carpetas. No crear otro repo. Mantener los archivos originales que no se reemplazan; no copiar node_modules, claves ni entornos virtuales.
2. Revisar cambios y hacer commit. Esta integración modifica varios archivos: no alcanza con pegar únicamente templates/index.html.
3. Si Vercel ya está conectado a observatorio-agro, usar el Preview Deployment de esa rama. La raíz debe ser la raíz del repositorio. Mantener vercel.json: declara el build estático React y la función Python existente; no configurar el proyecto como Next.js. Usar Node 22 y Python 3.12. El builder usa `vercel-build` -> `npm run build` y dist.
4. Variables opcionales: DOTS_CONTACT_URL con URL pública real del proyecto; FIRMS_MAP_KEY si ya se obtuvo. No hay claves necesarias para los adaptadores públicos básicos. .env.example no contiene secretos.
5. Abrir /, probar mapa, fuentes, exportación y PDF. Abrir /api/fuentes/estado. Confirmar en el log de Vercel que se construyeron frontend y función; no se ha validado un despliegue remoto desde aquí.
6. Cuando el Preview funcione, integrar la rama a main. El tiempo de despliegue depende de Vercel, no hay garantía de dos minutos.

## Alcance

Módulo de investigación en desarrollo. Catálogos nuevos no extraen índices raster; las fuentes con registro siguen pendientes. Consultas largas/raster y grandes históricos necesitarán trabajos asíncronos, almacenamiento y caché fuera de una función corta de Vercel. Aún no se agregaron cuentas de usuarios, persistencia de lotes, sensores, trazabilidad animal ni alertas operativas verificadas. Revisar condiciones de uso/cupos antes de escalar. La interfaz principal no usa los valores cero de respaldo del antiguo motor; /legacy y los dos endpoints originales son sólo compatibilidad histórica y no deben usarse como evidencia científica.

Archivos importantes: src/main.tsx, src/styles.css, research_connectors.py, research_routes.py, api/index.py, vercel.json. Matriz de 20 servicios: public/CONEXIONES-INVESTIGACION.md. Catálogo geográfico anterior: public/FUENTES-GLOBALES.md. Evidencia real: evidencia/.
