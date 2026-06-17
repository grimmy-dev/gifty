from typing import TypedDict

from utils.models import Contact, Product, ProfileSignals, RecommendedGift


class GraphState(TypedDict, total=False):
    contact: Contact
    signals: ProfileSignals
    queries: list[str]
    candidates: list[Product]
    validated: list[Product]
    ranked: list[RecommendedGift]
    logs: list[dict]
    review_feedback: str | None
    retried: bool


def with_log(state: GraphState, node: str, log: dict, **updates) -> dict:
    """Append a node log entry to the running trace and merge state updates."""
    updates["logs"] = state.get("logs", []) + [{"node": node, **log}]
    return updates
