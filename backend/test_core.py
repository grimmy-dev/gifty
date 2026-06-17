"""Tests for the trust-critical deterministic logic: safety guardrails, link
grounding, defensive parsing of model output, input validation, and retry
routing. All pure and offline; no LLM or network calls."""

import os

# Set before importing app modules: the LLM/search clients are constructed at
# import time and only need a non-empty key (no calls are made here).
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("TAVILY_API_KEY", "test-key")

import pytest
from pydantic import ValidationError

from analyze import SIGNALS_TO_AVOID, ContactAnalysis, scrub, to_signals
from graph.build import route_after_validate
from graph.retrieval import is_junk
from utils.models import GiftContext, RecommendedGift, RunRequest


# ---------- Guardrails: sensitive-signal filtering ----------


def test_scrub_drops_sensitive_signals():
    # The guard is a keyword backstop to the prompt: it drops signals mentioning
    # a sensitive *category* term. (It does not do NER on instance names; see
    # test_scrub_does_not_catch_instance_names for the documented limitation.)
    signals = [
        "Cricket enthusiast (posts about matches)",
        "Comments on his religion often",  # religio
        "Recovering from a health condition",  # health
        "Has young kids",  # kids
        "Active in conservative politics",  # politic
    ]
    assert scrub(signals) == ["Cricket enthusiast (posts about matches)"]


@pytest.mark.parametrize(
    "signal",
    [
        "Likely Hindu",  # named religion
        "Mentions being Muslim",
        "Recovering from a knee injury",  # health, no category keyword
        "Posts about his cancer recovery",
        "Recently divorced",  # family status
        "Engaged, fiance works in tech",
    ],
)
def test_scrub_catches_instance_terms(signal):
    # These slip past category keywords alone; the hardened term list catches them.
    assert scrub([signal]) == []


def test_scrub_is_not_exhaustive():
    # Honest limitation: the backstop is keyword-based, not NER. A phrasing with no
    # listed term still passes (the prompt is the primary defense). This documents
    # the boundary so widening SENSITIVE_TERMS stays a deliberate, tested change.
    uncaught = ["Going through a tough breakup right now"]
    assert scrub(uncaught) == uncaught


def test_scrub_keeps_clean_signals():
    clean = ["Enjoys specialty coffee", "Leads a design team", "Trail runner"]
    assert scrub(clean) == clean


def test_to_signals_scrubs_and_pins_avoid_list():
    analysis = ContactAnalysis(
        name="Aarav",
        strong_signals=["Cricket fan", "Married with two children"],
        weak_signals=["Likely religious", "May enjoy business books"],
        queries=["cricket gift india"],
    )
    out = to_signals(analysis)
    assert out.strong_signals == ["Cricket fan"]
    assert out.weak_signals == ["May enjoy business books"]
    # The avoid list is always present regardless of model output.
    assert out.signals_to_avoid == SIGNALS_TO_AVOID


# ---------- Grounding: drop non-store URLs ----------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc",
        "https://instagram.com/p/xyz",
        "https://www.reddit.com/r/gifts",
        "https://linkedin.com/in/someone",
    ],
)
def test_is_junk_flags_social_and_aggregator_hosts(url):
    assert is_junk(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.in/dp/B08XYZ",
        "https://www.flipkart.com/product/p/abc",
        "https://shop.example.com/item/123",
    ],
)
def test_is_junk_allows_real_stores(url):
    assert is_junk(url) is False


# ---------- Defensive parsing of model output ----------


def gift(**overrides) -> dict:
    """Minimal valid RecommendedGift payload, with field overrides."""
    base = {
        "rank": 1,
        "gift_name": "Cricket coffee table book",
        "product_url": "https://www.amazon.in/dp/B08XYZ",
        "store": "Amazon",
        "estimated_price": "INR 3999",
        "why_this_gift": "Matches the cricket signal and fits budget.",
        "personalisation_reasoning": "Posts about matches.",
        "personalised_message": "Thought this might resonate.",
        "confidence_score": 0.8,
    }
    return {**base, **overrides}


@pytest.mark.parametrize(
    "given,expected",
    [("LOW", "low"), ("Medium ", "medium"), ("HIGH", "high"), ("banana", "medium")],
)
def test_risk_level_normalisation(given, expected):
    assert RecommendedGift(**gift(risk_level=given)).risk_level == expected


def test_risk_level_defaults_to_low_when_absent():
    assert RecommendedGift(**gift()).risk_level == "low"


@pytest.mark.parametrize(
    "given,expected",
    [(0.87, 0.87), (87, 0.87), (150, 1.0), (-5, 0.0), ("0.5", 0.5)],
)
def test_confidence_score_normalisation(given, expected):
    assert RecommendedGift(**gift(confidence_score=given)).confidence_score == expected


# ---------- Input validation at the boundary ----------


def base_gift_context(**overrides) -> dict:
    base = {
        "occasion": "Thank you",
        "budget_min": 40,
        "budget_max": 80,
        "currency": "EUR",
        "country": "Germany",
    }
    return {**base, **overrides}


def test_gift_context_rejects_inverted_budget():
    with pytest.raises(ValidationError):
        GiftContext(**base_gift_context(budget_min=80, budget_max=40))


def test_gift_context_rejects_negative_budget():
    with pytest.raises(ValidationError):
        GiftContext(**base_gift_context(budget_min=-1))


def test_run_request_accepts_bare_contacts_array():
    contact = {
        "name": "Elena Rossi",
        "linkedin_profile": {},
        "gift_context": base_gift_context(),
    }
    parsed = RunRequest.model_validate([contact])
    assert len(parsed.contacts) == 1
    assert parsed.contacts[0].name == "Elena Rossi"


def test_run_request_rejects_empty_contacts():
    with pytest.raises(ValidationError):
        RunRequest.model_validate([])


# ---------- Retry routing ----------


def test_route_broadens_when_too_few_validated():
    assert route_after_validate({"validated": [object()]}) == "broaden_queries"


def test_route_recommends_when_enough_validated():
    state = {"validated": [object(), object(), object()]}
    assert route_after_validate(state) == "recommend"


def test_route_recommends_after_one_retry_even_if_still_few():
    # The retry flag prevents an infinite broaden/search loop.
    assert route_after_validate({"validated": [], "retried": True}) == "recommend"
