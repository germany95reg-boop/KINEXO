import asyncio
import re
from urllib.parse import quote
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="KINEXO Search", version="0.2.0")

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
        if license_id not in (1,2,3,4,5,6,7): return None
        files=v.get("files") or []
        if not files: return None
        url=files[0].get("fileUrl","")
        if not url.startswith("https://"): return None
        return {"id":ident,"title":v["name"],"url":url,"license":(v.get("licence") or {}).get("label"),"provider":"peertube"}
    limit=asyncio.Semaphore(5)
    return [x for x in await asyncio.gather(*(resolve(d) for d in r.json().get("data",[])),return_exceptions=True) if isinstance(x,dict)]

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/search")
async def search(q: str = Query(min_length=2,max_length=150)):
    async with httpx.AsyncClient(timeout=12,follow_redirects=True) as client:
        groups=await asyncio.gather(archive(client,q),peertube(client,q),return_exceptions=True)
    results={}
    failed=[]
    for provider,group in zip(("archive","peertube"),groups):
        if isinstance(group,Exception):
            failed.append(provider)
            continue
        for item in group:
            key=" ".join(item["title"].casefold().split())
            if key not in results: results[key]={**item,"alternatives":[]}
            else: results[key]["alternatives"].append(item)
    return JSONResponse({"results":list(results.values()),"unavailable_providers":failed})
