"""Mount this router in the existing FastAPI application."""
import os
import asyncio
import httpx
from .stream_probe import probe
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
    hosts = frozenset(h.strip().lower() for h in os.environ.get(
        "KINEXO_PROBE_HOSTS", "").split(",") if h.strip())
    results = results[:20]
    limit = asyncio.Semaphore(5)
    async with httpx.AsyncClient(trust_env=False) as client:
        async def check(stream):
            async with limit:
                status = await probe(client, stream.url, hosts)
                return {**asdict(stream), "availability": status}
        try:
            rows = await asyncio.wait_for(
                asyncio.gather(*(check(s) for s in results)), timeout=24)
        except asyncio.TimeoutError:
            rows = [{**asdict(s), "availability": "unverified"} for s in results]
    order = {"reachable": 0, "unverified": 1, "unavailable": 2}
    rows.sort(key=lambda r: (order[r["availability"]], -r["height"]))
    return {"query": q, "count": len(rows), "streams": rows,
            "preferred": next((r for r in rows if r["availability"] == "reachable"), None)}
