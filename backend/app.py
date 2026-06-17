"""FastAPI application exposing the recommendation workflow."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from analyze import SIGNALS_TO_AVOID, ContactAnalysis, analyze_batch, to_signals
from config import settings
from graph.build import graph
from graph.state import GraphState
from utils.db import create_run, get_run, init_db, update_run
from utils.errors import register_handlers
from utils.models import (
    APIError,
    Contact,
    CreateRunsResponse,
    EditRequest,
    HumanReview,
    ProfileSignals,
    Recommendation,
    RegenerateRequest,
    ReviewRequest,
    RunRecord,
    RunRequest,
    RunSummary,
    SearchTrace,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Every non-2xx response is documented as the shared error envelope.
app = FastAPI(
    title="Gifty",
    lifespan=lifespan,
    responses={400: {"model": APIError}, 404: {"model": APIError}, 409: {"model": APIError}, 422: {"model": APIError}},
)
register_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def build_run_data(contact: Contact, signals: ProfileSignals, queries: list[str], state: GraphState) -> dict:
    """Assemble the persisted run payload: result schema + trace + replayable inputs."""
    data = assemble(contact, state).model_dump()
    data["trace"] = state.get("logs", [])
    # Persist the graph inputs so regeneration is self-contained and survives restarts.
    data["inputs"] = {
        "contact": contact.model_dump(),
        "signals": signals.model_dump(),
        "queries": queries,
    }
    return data


async def run_contact(contact: Contact, signals: ProfileSignals, queries: list[str], user_id: str) -> RunSummary:
    """Run one contact through the graph and persist; isolate failures."""
    try:
        state = await graph.ainvoke({"contact": contact, "signals": signals, "queries": queries})
        data = build_run_data(contact, signals, queries, state)
        run_id = await asyncio.to_thread(create_run, user_id, contact.name, data)
        return RunSummary(run_id=run_id, contact_name=contact.name, status="pending_review")
    except Exception as exc:
        logging.exception("contact %s failed", contact.name)
        run_id = await asyncio.to_thread(
            create_run, user_id, contact.name, {"contact_name": contact.name, "error": str(exc)}, status="failed"
        )
        return RunSummary(run_id=run_id, contact_name=contact.name, status="failed", error=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def analyze_contacts(contacts: list[Contact]) -> list[ContactAnalysis | None]:
    """Run the batched analyze stage, returning one analysis per contact, in order."""
    batches = [contacts[i : i + settings.batch_size] for i in range(0, len(contacts), settings.batch_size)]
    analysed = await asyncio.gather(*(asyncio.to_thread(analyze_batch, b) for b in batches))
    # Align positionally (not by name): duplicate names can't collide, and a short
    # model response degrades to None (safe default) for the unmatched slots.
    out: list[ContactAnalysis | None] = []
    for batch, (analyses, _log) in zip(batches, analysed):
        out.extend(analyses[i] if i < len(analyses) else None for i in range(len(batch)))
    return out


def signals_and_queries(analysis: ContactAnalysis | None) -> tuple[ProfileSignals, list[str]]:
    """Derive graph inputs from an analysis, falling back to a safe default."""
    if not analysis:
        return ProfileSignals(signals_to_avoid=SIGNALS_TO_AVOID), []
    return to_signals(analysis), analysis.queries


@app.post("/runs", response_model=CreateRunsResponse)
async def create_runs(req: RunRequest) -> CreateRunsResponse:
    """Batched analyze, then run each contact's pipeline concurrently."""
    analyses = await analyze_contacts(req.contacts)
    sem = asyncio.Semaphore(settings.max_concurrency)

    async def guarded(contact: Contact, analysis: ContactAnalysis | None) -> RunSummary:
        async with sem:
            signals, queries = signals_and_queries(analysis)
            return await run_contact(contact, signals, queries, req.user_id)

    runs = await asyncio.gather(*(guarded(c, a) for c, a in zip(req.contacts, analyses)))
    return CreateRunsResponse(runs=list(runs))


@app.get("/runs/{run_id}", response_model=RunRecord)
def read_run(run_id: str) -> dict:
    return _load(run_id)


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


async def load_regen_inputs(run_id: str) -> tuple[Contact, ProfileSignals, dict, str]:
    """Load a run's stored graph inputs for regeneration; 409 if none were saved."""
    run = await asyncio.to_thread(_load, run_id)
    inputs = run["data"].get("inputs")
    if not inputs:
        raise HTTPException(status_code=409, detail="run has no stored inputs to regenerate from")
    return Contact(**inputs["contact"]), ProfileSignals(**inputs["signals"]), inputs, run["user_id"]


@app.post("/runs/{run_id}/approve", response_model=RunRecord)
def approve_run(run_id: str, req: ReviewRequest) -> dict:
    run = _load(run_id)
    data = run["data"]
    _set_review(data, "approved", req.note)
    update_run(run_id, status="approved", data=data)
    return get_run(run_id)


@app.post("/runs/{run_id}/reject", response_model=RunRecord)
def reject_run(run_id: str, req: ReviewRequest) -> dict:
    run = _load(run_id)
    data = run["data"]
    _set_review(data, "rejected", req.note)
    update_run(run_id, status="rejected", data=data)
    return get_run(run_id)


@app.post("/runs/{run_id}/edit", response_model=RunRecord)
def edit_run(run_id: str, req: EditRequest) -> dict:
    """Replace the recommended gifts with reviewer-edited ones."""
    run = _load(run_id)
    data = run["data"]
    data["recommended_gifts"] = [g.model_dump() for g in req.recommended_gifts]
    _set_review(data, "edited", req.note)
    update_run(run_id, status="edited", data=data)
    return get_run(run_id)


@app.post("/runs/{run_id}/regenerate", response_model=RunRecord)
async def regenerate_run(run_id: str, req: RegenerateRequest) -> dict:
    """Re-run the pipeline for a contact, steered by optional reviewer feedback."""
    contact, signals, inputs, _ = await load_regen_inputs(run_id)
    state = await graph.ainvoke(
        {
            "contact": contact,
            "signals": signals,
            "queries": inputs["queries"],
            "review_feedback": req.feedback or None,
        }
    )
    data = build_run_data(contact, signals, inputs["queries"], state)
    await asyncio.to_thread(update_run, run_id, status="pending_review", data=data)
    return await asyncio.to_thread(get_run, run_id)


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_run(
    contact: Contact,
    signals: ProfileSignals,
    queries: list[str],
    user_id: str,
    *,
    run_id: str | None = None,
    feedback: str | None = None,
):
    """Stream a contact's graph run as SSE: one `node` event per node, then `result`.

    Persists at the end (create on a fresh run, update when regenerating) so the
    streamed run is reviewable exactly like a non-streamed one.
    """
    init: GraphState = {"contact": contact, "signals": signals, "queries": queries}
    if feedback:
        init["review_feedback"] = feedback
    final_state: GraphState = {}
    try:
        async for mode, chunk in graph.astream(init, stream_mode=["updates", "values"]):
            if mode == "updates":
                for node, update in chunk.items():
                    logs = (update or {}).get("logs") or []
                    yield sse("node", {"contact_name": contact.name, "node": node, "log": logs[-1] if logs else {}})
            else:
                final_state = chunk
    except Exception as exc:
        logging.exception("stream for %s failed", contact.name)
        yield sse("error", {"contact_name": contact.name, "error": str(exc)})
        return

    data = build_run_data(contact, signals, queries, final_state)
    if run_id:
        await asyncio.to_thread(update_run, run_id, status="pending_review", data=data)
    else:
        run_id = await asyncio.to_thread(create_run, user_id, contact.name, data)
    yield sse("result", {"run_id": run_id, "contact_name": contact.name, "status": "pending_review", **data})


@app.post("/runs/stream")
async def create_runs_stream(req: RunRequest) -> StreamingResponse:
    """Run all contacts over one SSE connection (UI path).

    Analyze once, then walk contacts sequentially so the stream stays light: a
    single connection, one graph at a time. Every event is tagged with the
    contact it belongs to, and each contact ends with its own `result`.
    """
    contacts = req.contacts

    async def gen():
        yield sse("start", {"contacts": [c.name for c in contacts]})
        analyses = await analyze_contacts(contacts)
        yield sse("analyze", {"contacts": [c.name for c in contacts]})
        for contact, analysis in zip(contacts, analyses):
            signals, queries = signals_and_queries(analysis)
            async for ev in stream_run(contact, signals, queries, req.user_id):
                yield ev

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/runs/{run_id}/regenerate/stream")
async def regenerate_run_stream(run_id: str, req: RegenerateRequest) -> StreamingResponse:
    """Re-run a contact from stored inputs with live SSE progress, steered by feedback."""
    contact, signals, inputs, user_id = await load_regen_inputs(run_id)

    async def gen():
        yield sse("start", {"contact_name": contact.name})
        async for ev in stream_run(
            contact, signals, inputs["queries"], user_id, run_id=run_id, feedback=req.feedback or None
        ):
            yield ev

    return StreamingResponse(gen(), media_type="text/event-stream")
