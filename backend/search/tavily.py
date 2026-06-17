"""Search interface. Tavily backend; extend here for a DDG fallback later."""

from config import settings
from utils.models import Product


class TavilySearch:
    """Wraps the Tavily client and maps results to Product."""

    def __init__(self) -> None:
        from tavily import TavilyClient

        self.client = TavilyClient(api_key=settings.tavily_api_key)

    def search(self, query: str, max_results: int | None = None) -> list[Product]:
        """Run a web search and return product candidates."""
        res = self.client.search(
            query=query,
            max_results=max_results or settings.search_max_results,
            search_depth="basic",
        )
        return [
            Product(
                title=r.get("title", "").strip() or r.get("url", ""),
                url=r.get("url", ""),
                snippet=r.get("content", "")[:500],
            )
            for r in res.get("results", [])
        ]


search_client = TavilySearch()
