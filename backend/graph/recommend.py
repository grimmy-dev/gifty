"""Pipeline node that ranks gifts and writes notes in a single call."""

from pydantic import BaseModel

from graph.state import GraphState, with_log
from llm.client import llm
from utils.models import RecommendedGift
from utils.prompts import RECOMMEND_SYS, contact_summary


class RecommendOut(BaseModel):
    gifts: list[RecommendedGift]


def recommend(state: GraphState) -> dict:
    """Pick the top 3 validated gifts with reasoning and personalised notes."""
    validated, c, sig = state["validated"], state["contact"], state["signals"]
    # Nothing survived validation: skip the LLM call and let the API flag for review.
    if not validated:
        return with_log(state, "recommend", {"count": 0}, ranked=[])
    # One line per candidate so the model ranks only from real, checked products.
    listing = "\n".join(
        f"- {p.title} | {p.url} | price={p.price} | store={p.store}" for p in validated
    )
    # On regenerate, fold the reviewer's rejection note into the prompt.
    feedback = state.get("review_feedback")
    feedback_block = (
        f"\n\nThe reviewer rejected the previous picks with this feedback - honour it:\n{feedback}"
        if feedback
        else ""
    )
    user = (
        f"{contact_summary(c)}\n\nSignals: strong={sig.strong_signals} weak={sig.weak_signals}\n\n"
        f"Validated candidates:\n{listing}{feedback_block}"
    )
    # Smart tier does the ranking + note writing; cap at 3 even if it returns more.
    out, log = llm.generate("smart", RECOMMEND_SYS, user, RecommendOut, max_tokens=3000)
    return with_log(state, "recommend", log, ranked=out.gifts[:3])
