"""Pipeline node that ranks gifts and writes notes in a single call."""

from pydantic import BaseModel

from graph.state import GraphState, with_log
from llm.client import llm
from utils.models import RecommendedGift
from utils.prompts import RECOMMEND_SYS, contact_summary


class RankedGift(BaseModel):
    rank: int
    gift_name: str
    product_url: str
    store: str
    estimated_price: str
    why_this_gift: str
    personalisation_reasoning: str
    personalised_message: str
    confidence_score: float
    risk_level: str
    assumptions: list[str]


class RecommendOut(BaseModel):
    gifts: list[RankedGift]


def recommend(state: GraphState) -> dict:
    """Pick the top 3 validated gifts with reasoning and personalised notes."""
    validated, c, sig = state["validated"], state["contact"], state["signals"]
    if not validated:
        return with_log(state, "recommend", {"count": 0}, ranked=[])
    listing = "\n".join(f"- {p.title} | {p.url} | price={p.price} | store={p.store}" for p in validated)
    user = (
        f"{contact_summary(c)}\n\nSignals: strong={sig.strong_signals} weak={sig.weak_signals}\n\n"
        f"Validated candidates:\n{listing}"
    )
    out, log = llm.generate("smart", RECOMMEND_SYS, user, RecommendOut, max_tokens=3000)
    gifts = [RecommendedGift(**g.model_dump()) for g in out.gifts[:3]]
    return with_log(state, "recommend", log, ranked=gifts)
