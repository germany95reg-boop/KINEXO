import asyncio
import re
import time
from collections import OrderedDict
from difflib import SequenceMatcher
from fastapi import HTTPException
from urllib.parse import quote
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

if __package__:
    from .discovery_api import router as discovery_router
else:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from server.discovery_api import router as discovery_router

app = FastAPI(title="KINEXO Search", version="0.5.0")
app.include_router(discovery_router)

async def archive(client, query):
    safe = re.sub(r"[^\w ]", " ", query)
    response = await client.get("https://archive.org/advancedsearch.php", params={"q": f'title:({safe}) AND mediatype:movies AND licenseurl:*creativecommons.org*', "fl[]": ["identifier","title","licenseurl"], "rows": 25,"output":"json"})
    response.raise_for_status()
    docs = response.json()["response"]["docs"]
    async def resolve(doc):
        ident = doc["identifier"]
        async with limit:
            r = await client.get("https://archive.org/metadata/"+quote(ident,safe=""))
            r.raise_for_status()
        files = [f for f in r.json().get("files",[]) if f.get("name","").lower().endswith(".mp4")]
        if not files: return None
        f = files[0]
        return {"id":ident,"title":doc.get("title",ident),"url":"https://archive.org/download/"+quote(ident,safe="")+"/"+quote(f["name"]),"license":doc.get("licenseurl"),"provider":"archive"}
    limit = asyncio.Semaphore(5)
    return [x for x in await asyncio.gather(*(resolve(d) for d in docs),return_exceptions=True) if isinstance(x,dict)]

async def peertube(client, query):
    r = await client.get("https://video.blender.org/api/v1/search/videos",params={"search":query,"count":20})
    r.raise_for_status()
    async def resolve(item):
        ident = item["uuid"]
        if not re.fullmatch(r"[a-fA-F0-9-]+",ident): return None
        async with limit:
            response = await client.get("https://video.blender.org/api/v1/videos/"+ident)
            response.raise_for_status()
        v=response.json()
        license_id=(v.get("licence") or {}).get("id")
        if license_id not in (1,2,3,4,5,6): return None
        files=v.get("files") or []
        urls=[f.get("fileUrl","") for f in files]
        urls += [p.get("playlistUrl","") for p in (v.get("streamingPlaylists") or [])]
        url=next((u for u in urls if isinstance(u,str) and u.startswith("https://")),None)
        if not url: return None
        return {"id":ident,"title":v["name"],"url":url,"license":(v.get("licence") or {}).get("label"),"provider":"peertube"}
    limit=asyncio.Semaphore(5)
    return [x for x in await asyncio.gather(*(resolve(d) for d in r.json().get("data",[])),return_exceptions=True) if isinstance(x,dict)]

cache=OrderedDict()

def normalize(s):
    return " ".join(re.findall(r"\w+",s.casefold()))

def relevance(q,title):
    q,t=normalize(q),normalize(title)
    if q==t: return 3.0
    if not q or not t: return 0.0
    return (1.0 if q in t else 0.0)+SequenceMatcher(None,q,t).ratio()

@app.get("/health")
def health():
    return {"status":"ok","version":app.version,"providers":["archive","peertube"]}

@app.get("/search")
async def search(q: str = Query(min_length=2,max_length=150)):
    q = " ".join(q.split())
    if len(q)<2: raise HTTPException(422,"Empty search")
    cache_key=q.casefold()
    saved=cache.get(cache_key)
    if saved and time.monotonic()-saved[0]<120:
        cache.move_to_end(cache_key)
        return JSONResponse(saved[1])
    async with httpx.AsyncClient(timeout=8,follow_redirects=True) as client:
        groups=await asyncio.gather(asyncio.wait_for(archive(client,q),18),asyncio.wait_for(peertube(client,q),18),return_exceptions=True)
    results={}
    failed=[]
    for provider,group in zip(("archive","peertube"),groups):
        if isinstance(group,Exception):
            failed.append(provider)
            continue
        for item in group:
            key=(normalize(item["title"]),item["provider"],item["id"])
            if key not in results: results[key]={**item,"alternatives":[]}
            else: results[key]["alternatives"].append(item)
    ranked=sorted(results.values(),key=lambda item: relevance(q,item["title"]),reverse=True)
    payload={"results":ranked[:40],"unavailable_providers":failed}
    if not failed:
        cache[cache_key]=(time.monotonic(),payload)
        cache.move_to_end(cache_key)
        while len(cache)>128: cache.popitem(last=False)
    return JSONResponse(payload,headers={"Cache-Control":"no-store" if failed else "public, max-age=60"})
