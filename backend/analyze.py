"""Batched signal extraction, query generation, and deterministic safety guard."""

from pydantic import BaseModel

from llm.client import llm
from utils.models import Contact, ProfileSignals
from utils.prompts import ANALYZE_SYS, batch_summary

# Deterministic guard: drop any signal mentioning a sensitive attribute, regardless of
# what the model returns. Cheap and reliable backstop to the prompt instruction.
SENSITIVE_TERMS = (
    "religio", "politic", "health", "illness", "medical", "ethnic", "race", "caste",
    "gender", "sexual", "pregnan", "marriage", "married", "wife", "husband", "family",
    "child", "kids", "disab",
)

SIGNALS_TO_AVOID = [
    "Do not infer religion, politics, health, ethnicity, gender, or family status",
    "Avoid overly personal or creepy personalisation",
]


class ContactAnalysis(BaseModel):
    name: str
    strong_signals: list[str]
    weak_signals: list[str]
    queries: list[str]


class BatchAnalysis(BaseModel):
    contacts: list[ContactAnalysis]


def scrub(signals: list[str]) -> list[str]:
    """Remove signals referencing sensitive attributes."""
    return [s for s in signals if not any(term in s.lower() for term in SENSITIVE_TERMS)]


def to_signals(analysis: ContactAnalysis) -> ProfileSignals:
    """Build guarded ProfileSignals from a raw analysis."""
    return ProfileSignals(
        strong_signals=scrub(analysis.strong_signals),
        weak_signals=scrub(analysis.weak_signals),
        signals_to_avoid=SIGNALS_TO_AVOID,
    )


def analyze_batch(contacts: list[Contact]) -> tuple[list[ContactAnalysis], dict]:
    """Analyse several contacts in one call. Returns (analyses, log)."""
    user = batch_summary(contacts)
    out, log = llm.generate("fast", ANALYZE_SYS, user, BatchAnalysis, max_tokens=4096)
    return out.contacts, {"node": "analyze", **log, "contacts": len(contacts)}
