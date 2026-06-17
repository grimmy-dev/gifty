"""Pipeline nodes for query generation, web search, and product validation."""

import asyncio
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from graph.state import GraphState, with_log
from llm.client import llm
from utils.models import Product
from utils.prompts import BROADEN_SYS, VALIDATE_SYS, contact_summary
from search.tavily import search_client

# Social/video/aggregator hosts that are never purchasable product pages.
JUNK_HOSTS = (
    "youtube.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
    "reddit.com", "pinterest.com", "linkedin.com", "quora.com", "goodreads.com",
)
# Codes meaning the page is genuinely gone. 403/406/429/503 are bot-blocks, not dead.
DEAD_CODES = {404, 410}


def is_junk(url: str) -> bool:
    """True if the URL host is a social/video/aggregator site, not a store."""
    host = urlparse(url).netloc.lower()
    return any(j in host for j in JUNK_HOSTS)


class Queries(BaseModel):
    queries: list[str]


class ValidatedProduct(BaseModel):
    url: str
    title: str
    price: str | None = None
    store: str | None = None
    relevant: bool
    reason: str = ""


class Validation(BaseModel):
    products: list[ValidatedProduct]


def broaden_queries(state: GraphState) -> dict:
    """Rewrite queries more broadly after a poor first search (one-shot retry)."""
    c, sig = state["contact"], state["signals"]
    user = (
        f"{contact_summary(c)}\n\nSignals: {sig.strong_signals + sig.weak_signals}\n"
        f"Queries that returned too few valid products: {state['queries']}"
    )
    out, log = llm.generate("fast", BROADEN_SYS, user, Queries)
    return with_log(state, "broaden_queries", log, queries=out.queries, retried=True)


def search(state: GraphState) -> dict:
    """Run each query and collect de-duplicated product candidates."""
    seen: set[str] = set()
    candidates: list[Product] = []
    for q in state["queries"]:
        for p in search_client.search(q):
            if p.url and p.url not in seen and not is_junk(p.url):
                seen.add(p.url)
                candidates.append(p)
    return with_log(state, "search", {"results": len(candidates)}, candidates=candidates)


async def validate_products(state: GraphState) -> dict:
    """Drop dead links, then keep candidates judged relevant and appropriate."""
    candidates = state["candidates"]
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=5, follow_redirects=True, headers=headers) as cl:

        async def alive(p: Product) -> Product | None:
            try:
                return None if (await cl.get(p.url)).status_code in DEAD_CODES else p
            except httpx.HTTPError:
                return None

        checked = await asyncio.gather(*(alive(p) for p in candidates))
    live = [p for p in checked if p][:20]
    if not live:
        return with_log(state, "validate_products", {"live": 0, "kept": 0}, validated=[])

    listing = "\n".join(f"{p.title} | {p.url} | {p.snippet}" for p in live)
    user = f"{contact_summary(state['contact'])}\n\nCandidates:\n{listing}"
    out, log = await asyncio.to_thread(llm.generate, "fast", VALIDATE_SYS, user, Validation, 3000)
    judged = {v.url: v for v in out.products}
    kept = [
        Product(title=p.title, url=p.url, price=judged[p.url].price, store=judged[p.url].store, snippet=p.snippet)
        for p in live
        if p.url in judged and judged[p.url].relevant
    ]
    return with_log(state, "validate_products", {**log, "live": len(live), "kept": len(kept)}, validated=kept)
