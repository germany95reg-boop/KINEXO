import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from .stream_discovery import Discovery, Stream
from .catalog_provider import CatalogProvider

class Provider:
    def __init__(self, streams):
        self.streams = streams
    async def search(self, title):
        return self.streams

class Broken:
    async def search(self, title):
        raise RuntimeError("unavailable")

class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_sort_and_deduplicate(self):
        low = Stream("Film", "https://example.org/a.mp4", "mp4", "test", 720)
        high = Stream("Film", "https://example.org/b.m3u8", "hls", "test", 1080)
        invalid = Stream("Film", "file:///tmp/a", "mp4", "test")
        engine = Discovery([Provider([low, high, invalid]), Provider([low]), Broken()])
        self.assertEqual(await engine.search("Film"), [high, low])
        self.assertEqual(await engine.search(" "), [])

    async def test_timeout(self):
        class Slow:
            async def search(self, title):
                await asyncio.sleep(1)
                return []
        self.assertEqual(await Discovery([Slow()], timeout=0.01).search("Film"), [])

    async def test_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps([
                {"title": "Example Film", "url": "https://example.org/a.mp4", "format": "MP4"},
                {"title": "Other", "url": "https://example.org/b.mp4", "format": "mp4"},
                None
            ]), encoding="utf-8")
            results = await Discovery([CatalogProvider(path)]).search("example film")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].format, "mp4")

if __name__ == "__main__":
    unittest.main()
