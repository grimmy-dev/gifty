"""Pydantic I/O schemas. Input = enriched contact; output = assignment result schema."""

from pydantic import BaseModel, Field

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
    budget_min: float
    budget_max: float
    currency: str
    country: str


class Contact(BaseModel):
    name: str
    role: str = ""
    company: str = ""
    location: str = ""
    linkedin_profile: LinkedInProfile
    relationship_context: RelationshipContext = RelationshipContext()
    gift_context: GiftContext


class RunRequest(BaseModel):
    user_id: str = "anonymous"
    contacts: list[Contact]


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
    confidence_score: float
    risk_level: str = "low"
    assumptions: list[str] = []


class HumanReview(BaseModel):
    status: str = "pending_review"
    available_actions: list[str] = Field(
        default_factory=lambda: ["approve", "reject", "edit", "regenerate"]
    )
    note: str = ""


class Recommendation(BaseModel):
    contact_name: str
    profile_signals: ProfileSignals
    search_trace: SearchTrace
    recommended_gifts: list[RecommendedGift] = []
    human_review: HumanReview = HumanReview()


# ---------- Internal (pipeline) ----------


class Product(BaseModel):
    title: str
    url: str
    price: str | None = None
    store: str | None = None
    snippet: str = ""
