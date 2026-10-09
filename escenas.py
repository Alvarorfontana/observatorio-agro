"""Endpoint catálogo Sentinel-2 STAC - v1.5 (catálogo, no raster procesado)"""
from fastapi import APIRouter, HTTPException
import research_connectors as c

router = APIRouter()

@router.get("")
async def obtener_escenas(lat: float, lon: float, limit: int = 5):
    try:
        result = c.scenes(lat, lon, max_results=limit)
        if result['status'] != 'recibido':
            raise HTTPException(status_code=502, detail=result.get('error', 'Error consultando catálogo'))
        return result['data']
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
