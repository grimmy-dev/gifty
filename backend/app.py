"""FastAPI application exposing the recommendation workflow.

A *run* is one submission (a batch) identified by `run_id`; every contact in it is
an *item* with its own id and review state. Batch endpoints live under `/runs`,
per-contact review under `/recommendations/{item_id}`.
"""

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
from utils.db import (
    create_item,
    get_batch,
    get_item,
    init_db,
    list_batches,
    new_run_id,
    update_item,
)
from utils.errors import register_handlers
from utils.models import (
    APIError,
    BatchRun,
    BatchSummary,
    Contact,
    CreateRunsResponse,
    EditRequest,
    HumanReview,
    ItemSummary,
    ProfileSignals,
    Recommendation,
    RegenerateRequest,
    ReviewRequest,
    RunItem,
    RunRequest,
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
    """Assemble the persisted item payload: result schema + trace + replayable inputs."""
    data = assemble(contact, state).model_dump()
    data["trace"] = state.get("logs", [])
    # Persist the graph inputs so regeneration is self-contained and survives restarts.
    data["inputs"] = {
        "contact": contact.model_dump(),
        "signals": signals.model_dump(),
        "queries": queries,
    }
    return data


async def run_contact(run_id: str, contact: Contact, signals: ProfileSignals, queries: list[str]) -> ItemSummary:
    """Run one contact through the graph and persist into the batch; isolate failures."""
    try:
        state = await graph.ainvoke({"contact": contact, "signals": signals, "queries": queries})
        data = build_run_data(contact, signals, queries, state)
        item_id = await asyncio.to_thread(create_item, run_id, contact.name, data)
        return ItemSummary(item_id=item_id, contact_name=contact.name, status="pending_review")
    except Exception as exc:
        logging.exception("contact %s failed", contact.name)
        item_id = await asyncio.to_thread(
            create_item, run_id, contact.name, {"contact_name": contact.name, "error": str(exc)}, status="failed"
        )
        return ItemSummary(item_id=item_id, contact_name=contact.name, status="failed", error=str(exc))


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
    """Batched analyze, then run each contact's pipeline concurrently in one batch run."""
    run_id = new_run_id()
    analyses = await analyze_contacts(req.contacts)
    sem = asyncio.Semaphore(settings.max_concurrency)

    async def guarded(contact: Contact, analysis: ContactAnalysis | None) -> ItemSummary:
        async with sem:
            signals, queries = signals_and_queries(analysis)
            return await run_contact(run_id, contact, signals, queries)

    items = await asyncio.gather(*(guarded(c, a) for c, a in zip(req.contacts, analyses)))
    return CreateRunsResponse(run_id=run_id, items=list(items))


@app.get("/runs", response_model=list[BatchSummary])
def list_runs(limit: int = 20) -> list[dict]:
    """Recent batch runs (newest first) for the history view."""
    return list_batches(min(max(limit, 1), 100))


@app.get("/runs/{run_id}", response_model=BatchRun)
def read_run(run_id: str) -> dict:
    """All contact items belonging to one batch run."""
    items = get_batch(run_id)
    if not items:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "created_at": items[0]["created_at"], "items": items}


def _load(item_id: str) -> dict:
    """Fetch a contact item or 404."""
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return item


def _set_review(data: dict, status: str, note: str) -> None:
    """Mirror review status/note into the embedded result schema."""
    review = data.setdefault("human_review", {})
    review["status"] = status
    if note:
        review["note"] = note


async def load_regen_inputs(item_id: str) -> tuple[Contact, ProfileSignals, dict, str]:
    """Load an item's stored graph inputs for regeneration; 409 if none were saved."""
    item = await asyncio.to_thread(_load, item_id)
    inputs = item["data"].get("inputs")
    if not inputs:
        raise HTTPException(status_code=409, detail="recommendation has no stored inputs to regenerate from")
    return Contact(**inputs["contact"]), ProfileSignals(**inputs["signals"]), inputs, item["run_id"]


@app.get("/recommendations/{item_id}", response_model=RunItem)
def read_item(item_id: str) -> dict:
    return _load(item_id)


@app.post("/recommendations/{item_id}/approve", response_model=RunItem)
def approve_item(item_id: str, req: ReviewRequest) -> dict:
    item = _load(item_id)
    data = item["data"]
    _set_review(data, "approved", req.note)
    update_item(item_id, status="approved", data=data)
    return get_item(item_id)


@app.post("/recommendations/{item_id}/reject", response_model=RunItem)
def reject_item(item_id: str, req: ReviewRequest) -> dict:
    item = _load(item_id)
    data = item["data"]
    _set_review(data, "rejected", req.note)
    update_item(item_id, status="rejected", data=data)
    return get_item(item_id)


@app.post("/recommendations/{item_id}/edit", response_model=RunItem)
def edit_item(item_id: str, req: EditRequest) -> dict:
    """Replace the recommended gifts with reviewer-edited ones."""
    item = _load(item_id)
    data = item["data"]
    data["recommended_gifts"] = [g.model_dump() for g in req.recommended_gifts]
    _set_review(data, "edited", req.note)
    update_item(item_id, status="edited", data=data)
    return get_item(item_id)


@app.post("/recommendations/{item_id}/regenerate", response_model=RunItem)
async def regenerate_item(item_id: str, req: RegenerateRequest) -> dict:
    """Re-run the pipeline for a contact, steered by optional reviewer feedback."""
    contact, signals, inputs, _ = await load_regen_inputs(item_id)
    state = await graph.ainvoke(
        {
            "contact": contact,
            "signals": signals,
            "queries": inputs["queries"],
            "review_feedback": req.feedback or None,
        }
    )
    data = build_run_data(contact, signals, inputs["queries"], state)
    await asyncio.to_thread(update_item, item_id, status="pending_review", data=data)
    return await asyncio.to_thread(get_item, item_id)


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_run(
    run_id: str,
    contact: Contact,
    signals: ProfileSignals,
    queries: list[str],
    *,
    item_id: str | None = None,
    feedback: str | None = None,
):
    """Stream a contact's graph run as SSE: one `node` event per node, then `result`.

    Persists at the end (create within the batch on a fresh run, update when
    regenerating) so the streamed run is reviewable exactly like a non-streamed one.
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
    if item_id:
        await asyncio.to_thread(update_item, item_id, status="pending_review", data=data)
    else:
        item_id = await asyncio.to_thread(create_item, run_id, contact.name, data)
    yield sse(
        "result",
        {"run_id": run_id, "item_id": item_id, "contact_name": contact.name, "status": "pending_review", **data},
    )


@app.post("/runs/stream")
async def create_runs_stream(req: RunRequest) -> StreamingResponse:
    """Run all contacts of one batch over a single SSE connection (UI path).

    Analyze once, then walk contacts sequentially so the stream stays light: a
    single connection, one graph at a time. Every event is tagged with the batch
    `run_id` and its contact, and each contact ends with its own `result`.
    """
    contacts = req.contacts
    run_id = new_run_id()

    async def gen():
        yield sse("start", {"run_id": run_id, "contacts": [c.name for c in contacts]})
        analyses = await analyze_contacts(contacts)
        yield sse("analyze", {"run_id": run_id, "contacts": [c.name for c in contacts]})
        for contact, analysis in zip(contacts, analyses):
            signals, queries = signals_and_queries(analysis)
            async for ev in stream_run(run_id, contact, signals, queries):
                yield ev

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/recommendations/{item_id}/regenerate/stream")
async def regenerate_item_stream(item_id: str, req: RegenerateRequest) -> StreamingResponse:
    """Re-run a contact from stored inputs with live SSE progress, steered by feedback."""
    contact, signals, inputs, run_id = await load_regen_inputs(item_id)

    async def gen():
        yield sse("start", {"run_id": run_id, "item_id": item_id, "contact_name": contact.name})
        async for ev in stream_run(
            run_id, contact, signals, inputs["queries"], item_id=item_id, feedback=req.feedback or None
        ):
            yield ev

    return StreamingResponse(gen(), media_type="text/event-stream")
