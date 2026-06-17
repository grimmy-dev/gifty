# Gifty — Backend

AI workflow that turns enriched LinkedIn-style contact data into the top 3 personalised,
**real purchasable** gift recommendations per contact — with reasoning, a personalised note,
and a human-review step. Built with FastAPI + LangGraph.

Gifts are never invented: a web search engine (Tavily) finds real product URLs, the pipeline
validates them, and the model only *reasons over* validated candidates.

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
| `POST` | `/runs` | run the pipeline for one or more contacts |
| `GET`  | `/runs/{id}` | fetch a contact's result (structured output + trace) |
| `POST` | `/runs/{id}/approve` | mark the result approved (optional `note`) |
| `POST` | `/runs/{id}/reject` | mark the result rejected (optional `note`) |
| `POST` | `/runs/{id}/edit` | replace `recommended_gifts` with reviewer-edited ones |
| `POST` | `/runs/{id}/regenerate` | re-run the pipeline, optionally steered by reviewer `feedback` |

### Example

```bash
curl -s -X POST localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d @sample_input.json

# -> {"runs":[{"run_id":"...","contact_name":"Aarav Mehta","status":"pending_review"}, ...]}

curl -s localhost:8000/runs/<run_id>
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
decouples review from the run, and makes review durable across restarts — the run row stores the
graph `inputs`, so `regenerate` re-runs without the original request.

`approve` / `reject` / `edit` are terminal. `regenerate` is the only looping action and is
**human-gated, not auto-looping** — each call is one deliberate reviewer action. Its *internal*
search retry is bounded (a single query-broaden pass per run); the number of regenerations is left
uncapped server-side by design and surfaced as a subtle warning in the UI.
