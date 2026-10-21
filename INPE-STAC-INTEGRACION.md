# DOTS — integración gratuita INPE (prototipo)
Se incorpora `inpe_stac.py` como conector de catálogo independiente, sin alterar las rutas existentes ni producción.

## Uso
```python
from inpe_stac import collections, scenes
cs = collections()
print(cs[:5])
# Seleccionar un ID REAL devuelto por collections(), preferentemente CBERS/Amazonia.
print(scenes(-28.507, -59.043, cs[0]["id"]))
```

Fuente oficial: https://data.inpe.br/bdc/stac/v1/docs

## Límites
- No requiere API key para las consultas públicas; disponibilidad y cobertura por colección deben verificarse.
- Los resultados son metadatos y enlaces a assets, no imágenes cargadas ni índices calculados.
- No añadir a la barra de capas hasta validar escena, raster y visualización sobre lote real.
- Mantener NASA GIBS, Landsat y Sentinel existentes; no duplicar sus conectores.
- Próximo paso: pruebas de red y licencia, endpoint Flask con envelope y tests, después raster COG y NDVI.
