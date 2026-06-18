"""Pydantic I/O schemas. Input = enriched contact; output = assignment result schema."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Closed vocabularies: keep these in sync with the pipeline and DB status values.
RiskLevel = Literal["low", "medium", "high"]
ReviewStatus = Literal["pending_review", "approved", "rejected", "edited", "failed"]
ReviewAction = Literal["approve", "reject", "edit", "regenerate"]

MAX_CONTACTS = 25  # Per-request cap; batched analyze + bounded concurrency downstream.

# ---------- Input ----------


class Experience(BaseModel):
    title: str = ""
    company: str = ""
    description: str = ""


class LinkedInProfile(BaseModel):
    headline: str = ""
    about: str = ""
    experience: list[Experience] = []
    recent_posts: list[str] = []
    recent_comments: list[str] = []
    engaged_topics: list[str] = []


class RelationshipContext(BaseModel):
    relationship_type: str = ""
    last_interaction: str = ""
    business_goal: str = ""


class GiftContext(BaseModel):
    occasion: str = ""
    budget_min: float = Field(ge=0)
    budget_max: float = Field(ge=0)
    currency: str
    country: str

    @model_validator(mode="after")
    def check_budget(self) -> "GiftContext":
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be >= budget_min")
        return self


class Contact(BaseModel):
    name: str
    role: str = ""
    company: str = ""
    location: str = ""
    linkedin_profile: LinkedInProfile
    relationship_context: RelationshipContext = RelationshipContext()
    gift_context: GiftContext


class RunRequest(BaseModel):
    contacts: list[Contact] = Field(min_length=1, max_length=MAX_CONTACTS)

    @model_validator(mode="before")
    @classmethod
    def accept_bare_array(cls, data: object) -> object:
        """Allow posting a raw `[ {contact}, ... ]` as well as `{contacts: [...]}`."""
        if isinstance(data, list):
            return {"contacts": data}
        return data


class ReviewRequest(BaseModel):
    """Approve/reject payload; note is an optional reviewer comment."""

    note: str = ""


class RegenerateRequest(BaseModel):
    """Re-run a contact's pipeline, optionally steered by reviewer feedback."""

    feedback: str = ""


# ---------- Output ----------


class ProfileSignals(BaseModel):
    strong_signals: list[str] = []
    weak_signals: list[str] = []
    signals_to_avoid: list[str] = []


class SearchTrace(BaseModel):
    queries_used: list[str] = []
    products_considered_count: int = 0


class RecommendedGift(BaseModel):
    rank: int
    gift_name: str
    product_url: str
    store: str
    estimated_price: str
    why_this_gift: str
    personalisation_reasoning: str
    personalised_message: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel = "low"
    assumptions: list[str] = []

    @field_validator("risk_level", mode="before")
    @classmethod
    def norm_risk(cls, v: object) -> object:
        """Tolerate LLM casing/variants; fall back to the cautious middle."""
        if isinstance(v, str):
            v = v.strip().lower()
        return v if v in ("low", "medium", "high") else "medium"

    @field_validator("confidence_score", mode="before")
    @classmethod
    def norm_confidence(cls, v: object) -> object:
        """Accept 0-1 or a 0-100 percentage; clamp into [0, 1]."""
        try:
            f = float(v)  # type: ignore[arg-type]
        except TypeError, ValueError:
            return v
        if f > 1.0:
            f /= 100.0
        return max(0.0, min(1.0, f))


class HumanReview(BaseModel):
    status: ReviewStatus = "pending_review"
    available_actions: list[ReviewAction] = Field(
        default_factory=lambda: ["approve", "reject", "edit", "regenerate"]
    )
    note: str = ""


class Recommendation(BaseModel):
    contact_name: str
    profile_signals: ProfileSignals
    search_trace: SearchTrace
    recommended_gifts: list[RecommendedGift] = []
    ranking_reason: str = ""  # One-line rationale for the ranking order.
    human_review: HumanReview = HumanReview()


# ---------- Internal (pipeline) ----------


class Product(BaseModel):
    title: str
    url: str
    price: str | None = None
    store: str | None = None
    snippet: str = ""


# ---------- API responses ----------


class ItemSummary(BaseModel):
    """One contact's outcome within a batch, as returned by the create endpoint."""

    item_id: str
    contact_name: str
    status: ReviewStatus
    error: str | None = None


class CreateRunsResponse(BaseModel):
    run_id: str
    items: list[ItemSummary]


class RunItem(BaseModel):
    """A persisted contact recommendation. `data` holds the result schema plus
    trace/inputs (or an error). `run_id` is the batch it belongs to."""

    id: str
    run_id: str
    contact_name: str
    status: ReviewStatus
    created_at: str
    data: dict[str, Any]


class BatchRun(BaseModel):
    """A full batch run: every contact item submitted together."""

    run_id: str
    created_at: str
    items: list[RunItem]


# ---------- Compact payloads (cards) ----------


class CompactGift(BaseModel):
    """Card-sized gift: always shown fields, plus detail only on the top pick."""

    rank: int
    gift_name: str
    product_url: str
    store: str
    estimated_price: str
    why_this_gift: str
    confidence_score: float
    risk_level: RiskLevel
    # Populated for rank 1 only; None/empty for ranks 2-3 to keep cards light.
    personalisation_reasoning: str | None = None
    personalised_message: str | None = None
    assumptions: list[str] = []


class CompactRecommendation(BaseModel):
    """Result schema without `inputs`/`trace`, with trimmed gifts."""

    contact_name: str
    profile_signals: ProfileSignals = ProfileSignals()
    search_trace: SearchTrace = SearchTrace()
    recommended_gifts: list[CompactGift] = []
    ranking_reason: str = ""
    human_review: HumanReview = HumanReview()


class CompactItem(BaseModel):
    """A persisted item with its result compacted for card rendering."""

    id: str
    run_id: str
    contact_name: str
    status: ReviewStatus
    created_at: str
    data: dict[str, Any]  # compact result, or {contact_name, error} for failures


class CompactBatchRun(BaseModel):
    """A batch run whose items carry compact results only."""

    run_id: str
    created_at: str
    items: list[CompactItem]


# ---------- Usage (detail page) ----------


class ModelUsage(BaseModel):
    model: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    ms: int = 0


class Usage(BaseModel):
    """Per-model token/latency rollup plus run totals, derived from the trace."""

    by_model: list[ModelUsage] = []
    totals: ModelUsage = ModelUsage(model="total")


class RunItemDetail(RunItem):
    """Full item (result + trace + inputs) plus the derived usage rollup."""

    usage: Usage = Usage()


class ContactStatus(BaseModel):
    item_id: str
    contact_name: str
    status: ReviewStatus


class BatchSummary(BaseModel):
    """Lightweight recent-batch listing for the history view."""

    run_id: str
    created_at: str
    contacts: list[ContactStatus]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class APIError(BaseModel):
    """Single error envelope returned for every non-2xx response."""

    error: ErrorBody


# ---------- Shape helpers ----------

# Heavy per-gift fields stripped from ranks 2-3 on cards.
_GIFT_DETAIL = ("personalisation_reasoning", "personalised_message", "assumptions")
_DROP = ("inputs", "trace")


def compact_of(data: dict) -> dict:
    """Strip `inputs`/`trace` and trim ranks 2-3 to card-sized gifts.

    Failed items (no `recommended_gifts`) are returned untouched except for the
    dropped keys.
    """
    if "recommended_gifts" not in data:
        return {k: v for k, v in data.items() if k not in _DROP}
    gifts = []
    for g in data["recommended_gifts"]:
        compact = {k: v for k, v in g.items() if k not in _GIFT_DETAIL}
        if g.get("rank") == 1:
            compact.update({k: g.get(k) for k in _GIFT_DETAIL})
        gifts.append(compact)
    return {
        k: v for k, v in data.items() if k not in _DROP
    } | {"recommended_gifts": gifts}


def usage_of(trace: list[dict]) -> dict:
    """Roll up per-model calls/tokens/ms from the persisted trace, with totals."""
    by_model: dict[str, dict] = {}
    for entry in trace:
        model = entry.get("model")
        if not model:  # search/no-op nodes carry no model.
            continue
        agg = by_model.setdefault(
            model,
            {"model": model, "calls": 0, "tokens_in": 0, "tokens_out": 0, "ms": 0},
        )
        agg["calls"] += 1
        for k in ("tokens_in", "tokens_out", "ms"):
            agg[k] += entry.get(k, 0)
    models = list(by_model.values())
    totals = {"model": "total", "calls": 0, "tokens_in": 0, "tokens_out": 0, "ms": 0}
    for m in models:
        for k in ("calls", "tokens_in", "tokens_out", "ms"):
            totals[k] += m[k]
    return {"by_model": models, "totals": totals}
