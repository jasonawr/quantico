from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET

import httpx


def _text(node, path: str) -> str:
    v = node.findtext(path)
    return v.strip() if isinstance(v, str) else ""


async def fetch_news(query: str = "bitcoin", max_items: int = 10) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:1d&hl=en-US&gl=US&ceid=US:en"
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    items = []
    for item in root.findall("./channel/item")[:max_items]:
        items.append(
            {
                "title": _text(item, "title"),
                "link": _text(item, "link"),
                "pub_date": _text(item, "pubDate"),
                "source": _text(item, "source"),
            }
        )
    return items
