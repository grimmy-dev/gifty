"""Shared state passed between graph nodes, plus the trace-logging helper."""

from typing import TypedDict

from utils.models import Contact, Product, ProfileSignals, RecommendedGift


class GraphState(TypedDict, total=False):
    # total=False: each node reads what it needs and returns only the keys it sets.
    contact: Contact
    signals: ProfileSignals
    queries: list[str]
    candidates: list[Product]  # Raw search hits.
    validated: list[Product]  # Candidates that survived link + relevance checks.
    ranked: list[RecommendedGift]  # Final top picks with notes.
    logs: list[dict]  # Per-node trace, accumulated across the run.
    review_feedback: str | None  # Reviewer steer on regenerate.
    retried: bool  # Set once broaden_queries runs, caps the retry at one.


def with_log(state: GraphState, node: str, log: dict, **updates) -> dict:
    """Append a node log entry to the running trace and merge state updates."""
    updates["logs"] = state.get("logs", []) + [{"node": node, **log}]
    return updates
