"""Provider for operator-managed catalogs of authorized media."""
import json
from pathlib import Path
from .stream_discovery import Stream

class CatalogProvider:
    def __init__(self, path: Path, name: str = "catalog"):
        self.path = path
        self.name = name

    async def search(self, title: str) -> list[Stream]:
        import asyncio
        entries = await asyncio.to_thread(self._load)
        query = title.casefold().split()
        results = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = item.get("title")
            url = item.get("url")
            fmt = item.get("format")
            if not all(isinstance(x, str) for x in (name, url, fmt)):
                continue
            if not all(word in name.casefold() for word in query):
                continue
            height = item.get("height", 0)
            language = item.get("language", "")
            results.append(Stream(name, url, fmt.lower(), self.name,
                height if isinstance(height, int) and height >= 0 else 0,
                language if isinstance(language, str) else ""))
        return results

    def _load(self):
        with self.path.open(encoding="utf-8") as source:
            data = json.load(source)
        return data if isinstance(data, list) else []
