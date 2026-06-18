"""Shared state passed between graph nodes, plus trace/narration helpers."""

import logging
from typing import TypedDict

from langgraph.config import get_stream_writer

from utils.models import Contact, Product, ProfileSignals, RecommendedGift

log = logging.getLogger("gifty.graph")


class GraphState(TypedDict, total=False):
    # total=False: each node reads what it needs and returns only the keys it sets.
    contact: Contact
    signals: ProfileSignals
    queries: list[str]
    candidates: list[Product]  # Raw search hits.
    validated: list[Product]  # Candidates that survived link + relevance checks.
    ranked: list[RecommendedGift]  # Final top picks with notes.
    ranking_reason: str  # One-line rationale for the final ranking order.
    logs: list[dict]  # Per-node trace, accumulated across the run.
    review_feedback: str | None  # Reviewer steer on regenerate.
    retried: bool  # Set once broaden_queries runs, caps the retry at one.


def with_log(state: GraphState, node: str, log: dict, **updates) -> dict:
    """Append a node log entry to the running trace and merge state updates."""
    updates["logs"] = state.get("logs", []) + [{"node": node, **log}]
    return updates


def step(phase: str, detail: str, contact_name: str = "") -> None:
    """Narrate one work step to the SSE custom stream and the file log.

    Single helper so the live stream and the file log can't drift: every
    narration line is both emitted as a custom chunk and written to the trace.
    """
    get_stream_writer()(
        {"contact_name": contact_name, "phase": phase, "detail": detail}
    )
    log.debug(detail, extra={"runctx": f"-·{contact_name}"})
