"""Endpoints DOTS Agentic - v1.5"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import agentic_engine as engine

router = APIRouter()

class LoteRequest(BaseModel):
    lat: float
    lon: float
    prompt: str = "Informe integral"
    polygon: Optional[List[List[float]]] = None
    ina_id: Optional[str] = None
    water_assets: Optional[List[Dict[str, Any]]] = None
    nombre: str = "Lote"

@router.post("")
async def analizar(req: LoteRequest):
    try:
        result = engine.analyze(
            lat=req.lat, lon=req.lon,
            prompt=req.prompt,
            polygon=req.polygon,
            ina_id=req.ina_id,
            water_assets=req.water_assets
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pdf")
async def generar_pdf(req: LoteRequest):
    try:
        result = engine.analyze(
            lat=req.lat, lon=req.lon,
            prompt=req.prompt,
            polygon=req.polygon,
            ina_id=req.ina_id,
            water_assets=req.water_assets
        )
        pdf = engine.pdf_bytes(result, name=req.nombre)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{req.nombre}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def status():
    """Status rápido (solo fuentes básicas)."""
    import research_connectors as c
    lat, lon = -31.42, -64.18
    tests = {
        'clima': c.open_meteo_forecast(lat, lon),
        'suelo': c.soilgrids_properties(lat, lon),
        'escenas_sentinel': c.copernicus_stac_scenes(lat, lon),
        'nasa_firms': c.nasa_firms(lat, lon),
        'enso': c.enso_multisource(),
        'rios': c.usgs_flood_api(lat, lon),
    }
    return {
        'tested_at': tests['clima']['consulted_at'],
        'sources': {
            k: {'status': v['status'], 'error': v.get('error'), 'organism': v.get('organism')}
            for k, v in tests.items()
        }
    }
