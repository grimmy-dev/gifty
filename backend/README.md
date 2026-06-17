# Gifty — Backend

AI workflow that turns enriched LinkedIn-style contact data into the top 3 personalised,
**real purchasable** gift recommendations per contact — with reasoning, a personalised note,
and a human-review step. Built with FastAPI + LangGraph.

Gifts are never invented: a web search engine (Tavily) finds real product URLs, the pipeline
validates them, and the model only *reasons over* validated candidates.

One submission is a batch run (`run_id`); each contact in it is an item (`item_id`) with its own
result and review state.

## Architecture

Two stages, orchestrated by the API:

```
POST /runs (N contacts)
  │
  ├─ Stage 1  batched analyze (fast model)        # signals + queries for several contacts per call
  │            └─ deterministic safety guard       # drops sensitive signals (no LLM)
  │
  └─ Stage 2  per-contact graph (concurrent, Semaphore)
               search → validate → recommend
                            └─ retry once (broaden queries) if < 3 grounded products
```

- **analyze** (`analyze.py`): extracts strong/weak signals + search queries for a *batch* of
  contacts in one call, then a deterministic guard scrubs anything sensitive
  (religion, politics, health, ethnicity, gender, family).
- **search** (`graph/retrieval.py`): runs the queries through Tavily, drops social/video/aggregator
  hosts.
- **validate** (`graph/retrieval.py`): checks each URL is live (404/410 = dead; 403/503 bot-blocks
  are kept), then the model judges relevance, budget, country, and appropriateness.
- **broaden + retry**: if fewer than 3 products survive, queries are broadened and searched once
  more (bounded — single retry), then it recommends whatever survived.
- **recommend** (`graph/recommend.py`): ranks the top 3 and writes a personalised note per gift in
  one call, with confidence, risk, and assumptions.

Weak grounding is surfaced, not hidden: 0 gifts → `human_review.note` asks for human input;
fewer than 3 → a review warning.

### Layout
```
app.py              FastAPI app + orchestration (batching, concurrency, failure isolation)
analyze.py          batched signal/query extraction + deterministic guard
config.py           settings (env-driven)
graph/              LangGraph: state, build, retrieval + recommend nodes
llm/client.py       provider-agnostic client (Claude/Gemini), fast/smart tiers, retry + fallback
search/tavily.py    Tavily search wrapper
utils/              models (Pydantic I/O), prompts, db (SQLite), errors (retry)
```

## Setup

```bash
uv sync
cp .env.example .env      # then fill in keys
```

`.env`:
- `LLM_PROVIDER` — `claude` or `gemini`
- `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` — key for the chosen provider
- `TAVILY_API_KEY` — required for search
- `CORS_ORIGINS` — allowed frontend origins (JSON list; default `localhost:5173`)

The provider runs two tiers: a **fast** model for retrieval/prep (analyze, validate) and a
**smart** model for the recommendation. Switch providers with one env var; both are supported.

## Run

```bash
uv run uvicorn app:app --reload --port 8000
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | liveness |
| `POST` | `/runs` | run the pipeline for a batch of contacts |
| `GET`  | `/runs` | recent batch runs (`?limit=`, newest first) |
| `GET`  | `/runs/{run_id}` | fetch a batch: all contact items |
| `GET`  | `/recommendations/{item_id}` | fetch one contact's result (structured output + trace) |
| `POST` | `/recommendations/{item_id}/approve` | mark approved (optional `note`) |
| `POST` | `/recommendations/{item_id}/reject` | mark rejected (optional `note`) |
| `POST` | `/recommendations/{item_id}/edit` | replace `recommended_gifts` with reviewer-edited ones |
| `POST` | `/recommendations/{item_id}/regenerate` | re-run the pipeline, optionally steered by `feedback` |
| `POST` | `/runs/stream` | run a batch over one **SSE** connection (UI path) |
| `POST` | `/recommendations/{item_id}/regenerate/stream` | regenerate one contact with live **SSE** progress |

The request body is a bare contacts array or `{ "contacts": [...] }`.

### Errors

Every non-2xx response shares one envelope:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed", "details": [...] } }
```

`code` is machine-readable (`VALIDATION_ERROR`, `NOT_FOUND`, `CONFLICT`, `INTERNAL_ERROR`, …);
validation errors carry per-field `details`. `5xx` messages are generic — internals are logged,
never returned.

### Streaming (SSE)

`POST /runs` is the batch path (Postman/curl → fetch `GET /runs/{run_id}`). The UI uses the SSE path
for live "thinking": `POST /runs/stream` analyzes once, then walks the contacts **sequentially over
a single connection** (one graph at a time — kept deliberately light). It emits `start` (with the
batch `run_id`) → `analyze` → per contact a stream of `node` events (each tagged `contact_name`,
carrying that node's log: model, tokens, ms) and a `result` event with the batch `run_id`, the
contact's `item_id`, and full result. Streamed runs are persisted identically, so all review
endpoints apply afterwards. `regenerate/stream` does the same for one contact from stored inputs
(no re-analyze).

### Example

```bash
curl -s -X POST localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d @sample_input.json

# -> {"run_id":"...","items":[{"item_id":"...","contact_name":"Aarav Mehta","status":"pending_review"}, ...]}

curl -s localhost:8000/runs/<run_id>              # whole batch
curl -s localhost:8000/recommendations/<item_id>  # one contact
```

`sample_input.json` holds two contacts in different countries/currencies to exercise batching and
per-contact isolation. The result matches the assignment output schema (`profile_signals`,
`search_trace`, `recommended_gifts`, `human_review`) plus a `trace` array of per-node
model/token/latency logs.

Multiple contacts run concurrently; one contact failing returns `status: "failed"` for that
contact without affecting the others.

### Human review

The pipeline runs to completion and persists the result; review happens through separate
endpoints (above) rather than a LangGraph `interrupt()`. This keeps the graph a pure function,
decouples review from the run, and makes review durable across restarts — each item row stores the
graph `inputs`, so `regenerate` re-runs without the original request.

`approve` / `reject` / `edit` are terminal. `regenerate` is the only looping action and is
**human-gated, not auto-looping** — each call is one deliberate reviewer action. Its *internal*
search retry is bounded (a single query-broaden pass per run); the number of regenerations is left
uncapped server-side by design and surfaced as a subtle warning in the UI.
