"""LangGraph construction for the per-contact recommendation pipeline."""

from langgraph.graph import END, START, StateGraph

from graph.recommend import recommend
from graph.retrieval import broaden_queries, search, validate_products
from graph.state import GraphState

MIN_GIFTS = 3


def route_after_validate(state: GraphState) -> str:
    """Retry search once if too few products survived; otherwise recommend."""
    if state.get("retried") or len(state.get("validated", [])) >= MIN_GIFTS:
        return "recommend"
    return "broaden_queries"


def build_graph():
    """Compile the per-contact search/validate/recommend pipeline with one retry.

    Signals and queries come from the batched analyze stage as initial state.
    If validation yields fewer than MIN_GIFTS, queries are broadened and searched
    once more before recommending whatever survived.
    """
    g = StateGraph(GraphState)
    g.add_node("search", search)
    g.add_node("validate_products", validate_products)
    g.add_node("broaden_queries", broaden_queries)
    g.add_node("recommend", recommend)

    g.add_edge(START, "search")
    g.add_edge("search", "validate_products")
    g.add_conditional_edges(
        "validate_products",
        route_after_validate,
        {"recommend": "recommend", "broaden_queries": "broaden_queries"},
    )
    g.add_edge("broaden_queries", "search")
    g.add_edge("recommend", END)
    return g.compile()


graph = build_graph()
