"""FastAPI application exposing the recommendation workflow."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from analyze import SIGNALS_TO_AVOID, analyze_batch, to_signals
from config import settings
from graph.build import graph
from graph.state import GraphState
from utils.db import create_run, get_run, init_db, update_run
from utils.models import (
    Contact,
    EditRequest,
    HumanReview,
    ProfileSignals,
    Recommendation,
    RegenerateRequest,
    ReviewRequest,
    RunRequest,
    SearchTrace,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Gifty", lifespan=lifespan)


def assemble(contact: Contact, state: GraphState) -> Recommendation:
    """Build the result schema from final graph state, flagging weak grounding."""
    gifts = state.get("ranked") or []
    review = HumanReview()
    if not gifts:
        review.note = "No sufficiently grounded products found after retry. Needs human input."
    elif len(gifts) < 3:
        review.note = f"Only {len(gifts)} grounded option(s) met the criteria; review before sending."
    return Recommendation(
        contact_name=contact.name,
        profile_signals=state.get("signals") or ProfileSignals(),
        search_trace=SearchTrace(
            queries_used=state.get("queries", []),
            products_considered_count=len(state.get("candidates", [])),
        ),
        recommended_gifts=gifts,
        human_review=review,
    )


async def run_contact(contact: Contact, signals: ProfileSignals, queries: list[str], user_id: str) -> dict:
    """Run one contact through the graph and persist; isolate failures."""
    try:
        state = await graph.ainvoke({"contact": contact, "signals": signals, "queries": queries})
        data = assemble(contact, state).model_dump()
        data["trace"] = state.get("logs", [])
        # Persist the graph inputs so regeneration is self-contained and survives restarts.
        data["inputs"] = {
            "contact": contact.model_dump(),
            "signals": signals.model_dump(),
            "queries": queries,
        }
        run_id = create_run(user_id, contact.name, data)
        return {"run_id": run_id, "contact_name": contact.name, "status": "pending_review"}
    except Exception as exc:
        logging.exception("contact %s failed", contact.name)
        run_id = create_run(user_id, contact.name, {"contact_name": contact.name, "error": str(exc)}, status="failed")
        return {"run_id": run_id, "contact_name": contact.name, "status": "failed", "error": str(exc)}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/runs")
async def create_runs(req: RunRequest) -> dict:
    """Batched analyze, then run each contact's pipeline concurrently."""
    contacts = req.contacts
    batches = [contacts[i : i + settings.batch_size] for i in range(0, len(contacts), settings.batch_size)]
    analysed = await asyncio.gather(*(asyncio.to_thread(analyze_batch, b) for b in batches))
    by_name = {a.name: a for analyses, _log in analysed for a in analyses}

    sem = asyncio.Semaphore(settings.max_concurrency)

    async def guarded(contact: Contact) -> dict:
        async with sem:
            analysis = by_name.get(contact.name)
            signals = to_signals(analysis) if analysis else ProfileSignals(signals_to_avoid=SIGNALS_TO_AVOID)
            queries = analysis.queries if analysis else []
            return await run_contact(contact, signals, queries, req.user_id)

    runs = await asyncio.gather(*(guarded(c) for c in contacts))
    return {"runs": runs}


@app.get("/runs/{run_id}")
def read_run(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


def _load(run_id: str) -> dict:
    """Fetch a run or 404."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


def _set_review(data: dict, status: str, note: str) -> None:
    """Mirror review status/note into the embedded result schema."""
    review = data.setdefault("human_review", {})
    review["status"] = status
    if note:
        review["note"] = note


@app.post("/runs/{run_id}/approve")
def approve_run(run_id: str, req: ReviewRequest) -> dict:
    run = _load(run_id)
    data = run["data"]
    _set_review(data, "approved", req.note)
    update_run(run_id, status="approved", data=data)
    return get_run(run_id)


@app.post("/runs/{run_id}/reject")
def reject_run(run_id: str, req: ReviewRequest) -> dict:
    run = _load(run_id)
    data = run["data"]
    _set_review(data, "rejected", req.note)
    update_run(run_id, status="rejected", data=data)
    return get_run(run_id)


@app.post("/runs/{run_id}/edit")
def edit_run(run_id: str, req: EditRequest) -> dict:
    """Replace the recommended gifts with reviewer-edited ones."""
    run = _load(run_id)
    data = run["data"]
    data["recommended_gifts"] = [g.model_dump() for g in req.recommended_gifts]
    _set_review(data, "edited", req.note)
    update_run(run_id, status="edited", data=data)
    return get_run(run_id)


@app.post("/runs/{run_id}/regenerate")
async def regenerate_run(run_id: str, req: RegenerateRequest) -> dict:
    """Re-run the pipeline for a contact, steered by optional reviewer feedback."""
    run = _load(run_id)
    inputs = run["data"].get("inputs")
    if not inputs:
        raise HTTPException(status_code=409, detail="run has no stored inputs to regenerate from")
    contact = Contact(**inputs["contact"])
    signals = ProfileSignals(**inputs["signals"])
    state = await graph.ainvoke(
        {
            "contact": contact,
            "signals": signals,
            "queries": inputs["queries"],
            "review_feedback": req.feedback or None,
        }
    )
    data = assemble(contact, state).model_dump()
    data["trace"] = state.get("logs", [])
    data["inputs"] = inputs
    update_run(run_id, status="pending_review", data=data)
    return get_run(run_id)
