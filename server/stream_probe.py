"""Opt-in availability checks for operator-approved media hosts."""
from urllib.parse import urlsplit
import httpx

async def probe(client: httpx.AsyncClient, url: str, allowed_hosts: frozenset[str]) -> str:
    try:
        u = urlsplit(url)
        if (u.scheme != "https" or u.hostname not in allowed_hosts
                or u.username or u.password or u.port not in (None, 443)):
            return "unverified"
        async with client.stream("GET", url, headers={"Range": "bytes=0-1023"},
                                 follow_redirects=False, timeout=5) as response:
            if response.status_code not in (200, 206):
                return "unverified" if 300 <= response.status_code < 400 else "unavailable"
            mime = response.headers.get("content-type", "").split(";")[0].lower()
            if mime.startswith("video/") or mime in {
                "application/vnd.apple.mpegurl", "application/x-mpegurl",
                "application/dash+xml", "audio/mpegurl"
            }:
                return "reachable"
            return "unverified"
    except (httpx.HTTPError, ValueError):
        return "unavailable"
