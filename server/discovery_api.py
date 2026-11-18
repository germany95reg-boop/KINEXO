"""Mount this router in the existing FastAPI application."""
import os
from dataclasses import asdict
from pathlib import Path
from fastapi import APIRouter, Query
from .catalog_provider import CatalogProvider
from .stream_discovery import Discovery

router = APIRouter(prefix="/api/v2", tags=["discovery"])

def build_engine():
    paths = os.environ.get("KINEXO_CATALOGS", "").split(os.pathsep)
    return Discovery([CatalogProvider(Path(p), name=Path(p).stem)
                      for p in paths if p.strip()])

@router.get("/streams")
async def streams(q: str = Query(min_length=1, max_length=200)):
    results = await build_engine().search(q)
    return {"query": q, "count": len(results),
            "streams": [asdict(stream) for stream in results]}
