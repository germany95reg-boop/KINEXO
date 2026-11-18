"""Search configured authorized video catalogs; no arbitrary URL fetching."""
import asyncio
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Stream:
    title: str
    url: str
    format: str
    provider: str
    height: int = 0
    language: str = ""

class Provider(Protocol):
    async def search(self, title: str) -> list[Stream]: ...

class Discovery:
    def __init__(self, providers: list[Provider], timeout: float = 8):
        self.providers = providers
        self.timeout = timeout

    async def search(self, title: str) -> list[Stream]:
        title = title.strip()
        if not title or len(title) > 200:
            return []
        async def query(provider):
            try:
                return await asyncio.wait_for(provider.search(title), self.timeout)
            except Exception:
                return []
        results = await asyncio.gather(*(query(p) for p in self.providers))
        unique = {}
        for group in results:
            for stream in group:
                parsed = urlsplit(stream.url)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    continue
                if stream.format.lower() not in {"hls", "dash", "mp4"}:
                    continue
                unique.setdefault(stream.url, stream)
        return sorted(unique.values(), key=lambda s: s.height, reverse=True)
