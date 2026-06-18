# Gifty - Backend

An AI workflow that turns enriched LinkedIn-style contact data into the **top 3 personalised, real
purchasable gift recommendations** per contact - each with reasoning, a personalised note,
confidence, risk, and a human-review step.

Built with **FastAPI** and **LangGraph**. Gifts are never invented: a web search engine (Tavily)
supplies real product URLs, the pipeline validates them, and the model only *reasons over* the
validated candidates.

> **Terminology.** One submission is a **batch run** (`run_id`); each contact within it is an
> **item** (`item_id`) with its own structured result and review state.

---

## Highlights

- **Multi-step LangGraph pipeline** - analyze → search → validate → recommend, not a single prompt.
- **Grounded** - only live, validated product URLs reach the final ranking; nothing hallucinated.
- **Guardrails** - a deterministic filter strips sensitive signals (religion, politics, health,
  ethnicity, gender, family status) regardless of model output, backing the prompt instructions.
- **Honest under weak data** - fewer than 3 grounded products lowers confidence and flags for human
  input rather than faking certainty.
- **Provider-agnostic** - switch Claude ↔ Gemini with one env var; fast/smart model tiers.
- **Human-in-the-loop** - approve / reject / edit / regenerate via REST, durable across restarts.
- **Observable** - per-node model, token, and latency logs persisted in each run's trace.
- **Live progress** - Server-Sent Events stream node-by-node progress to the UI.

---

## Architecture

Two stages, orchestrated by the API:

```
POST /runs  (N contacts)
  │
  ├─ Stage 1 · batched analyze (fast model)          # signals + queries, several contacts per call
  │             └─ deterministic safety guard          # scrubs sensitive signals (no LLM)
  │
  └─ Stage 2 · per-contact graph (concurrent, bounded by a Semaphore)
                search → validate → recommend (reasoning model)
                             └─ retry once (broaden queries) if < 3 grounded products
```

| Step | File | What it does |
|------|------|--------------|
| **analyze** | `analyze.py` | Extracts strong/weak signals + search queries for a *batch* of contacts in one call, then a deterministic guard removes anything sensitive. |
| **search** | `graph/retrieval.py` | Runs queries through Tavily; drops social/video/aggregator hosts. |
| **validate** | `graph/retrieval.py` | Confirms each URL is live (404/410 = dead; 403/503 bot-blocks kept) behind an SSRF guard, then the model judges relevance, budget, country, and appropriateness. |
| **broaden + retry** | `graph/retrieval.py` | If fewer than 3 products survive, broadens queries and searches once more (single bounded retry). |
| **recommend** | `graph/recommend.py` | Ranks the top 3 and writes a personalised note per gift in one call, with confidence, risk, and assumptions. |

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
utils/              models (Pydantic I/O), prompts, db (SQLite), errors (retry + envelope)
test_core.py        offline tests: guardrails, grounding, parsing, validation, retry, SSRF
```

---

## Tech stack

Python 3.14 · FastAPI · LangGraph · Pydantic · SQLite · Anthropic / Google GenAI · Tavily ·
managed with [`uv`](https://docs.astral.sh/uv/) and linted with `ruff`.

---

## Prerequisites

- **Python ≥ 3.14**
- **[`uv`](https://docs.astral.sh/uv/getting-started/installation/)**
- API keys: an LLM provider (**Anthropic** *or* **Google Gemini**) and **[Tavily](https://tavily.com/)** (free tier) for search.

---

## Setup

```bash
cd backend
uv sync # install dependencies into .venv
cp .env.example .env # then fill in your keys
```

### Configuration (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | – | `claude` | `claude` or `gemini` |
| `ANTHROPIC_API_KEY` | if `claude` | – | Anthropic key |
| `GEMINI_API_KEY` | if `gemini` | – | Google Gemini key |
| `TAVILY_API_KEY` | yes | – | Tavily search key |
| `CORS_ORIGINS` | – | `localhost:5173`, `127.0.0.1:5173` | Allowed frontend origins (JSON list) |
| `CLAUDE_FAST` / `CLAUDE_SMART` | – | `claude-haiku-4-5` / `claude-sonnet-4-6` | Model overrides |
| `GEMINI_FAST` / `GEMINI_SMART` | – | see `.env.example` | Model overrides |

Each provider runs two tiers: a **fast** model for retrieval/prep (analyze, validate) and a
**smart** model for the final recommendation.

---

## Run

```bash
uv run uvicorn app:app --reload --port 8000
```

The API is then at `http://localhost:8000`. Interactive docs (Swagger UI) at `http://localhost:8000/docs`.
SQLite (`gifty.db`) is created automatically on first start.

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | Liveness |
| `POST` | `/runs` | Run the pipeline for a batch of contacts |
| `GET`  | `/runs` | Recent batch runs (`?limit=`, newest first) |
| `GET`  | `/runs/{run_id}` | Fetch a batch: all contact items |
| `GET`  | `/recommendations/{item_id}` | Fetch one contact's result (structured output + trace) |
| `POST` | `/recommendations/{item_id}/approve` | Mark approved (optional `note`) |
| `POST` | `/recommendations/{item_id}/reject` | Mark rejected (optional `note`) |
| `POST` | `/recommendations/{item_id}/edit` | Replace `recommended_gifts` with reviewer-edited ones |
| `POST` | `/recommendations/{item_id}/regenerate` | Re-run the pipeline, optionally steered by `feedback` |
| `POST` | `/runs/stream` | Run a batch over one **SSE** connection (UI path) |
| `POST` | `/recommendations/{item_id}/regenerate/stream` | Regenerate one contact with live **SSE** progress |

The request body is either a bare contacts array or `{ "contacts": [...] }`.

### Example

```bash
curl -s -X POST localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d @sample_input.json
# -> {"run_id":"...","items":[{"item_id":"...","contact_name":"Aarav Mehta","status":"pending_review"}, ...]}

curl -s localhost:8000/runs/<run_id> # whole batch
curl -s localhost:8000/recommendations/<item_id> # one contact's full result
```

`sample_input.json` holds two contacts in different countries/currencies to exercise batching and
per-contact isolation. Each result matches the assignment output schema (`profile_signals`,
`search_trace`, `recommended_gifts`, `human_review`) plus a `trace` array of per-node
model/token/latency logs.

Contacts run concurrently; if one fails it returns `status: "failed"` for that contact without
affecting the others.

### Streaming (SSE)

`POST /runs` is the batch path (curl/Postman → poll `GET /runs/{run_id}`). The UI uses the SSE path
for live progress: `POST /runs/stream` analyzes once, then walks contacts **sequentially over a
single connection** (one graph at a time). It emits `start` (with the batch `run_id`) → `analyze` →
per contact a stream of `node` events (each tagged `contact_name`, carrying that node's log) and a
`result` event with the `item_id` and full result. Streamed runs are persisted identically, so the
review endpoints apply afterwards. `regenerate/stream` does the same for one contact from stored
inputs (no re-analyze).

### Error format

Every non-2xx response shares one envelope:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed", "details": [] } }
```

`code` is machine-readable (`VALIDATION_ERROR`, `NOT_FOUND`, `CONFLICT`, `INTERNAL_ERROR`, …);
validation errors carry per-field `details`. `5xx` messages are generic - internals are logged,
never returned to the client.

---

## Human review

The pipeline runs to completion and persists the result; review happens through separate REST
endpoints rather than a LangGraph `interrupt()`. This keeps the graph a pure function, decouples
review from the run, and makes review durable across restarts - each item row stores the graph
`inputs`, so `regenerate` re-runs without the original request.

`approve` / `reject` / `edit` are terminal. `regenerate` is the only looping action and is
**human-gated, not auto-looping** - each call is one deliberate reviewer action. Its *internal*
search retry is bounded (a single query-broaden pass per run).

---

## Testing

```bash
uv run pytest
```

`test_core.py` is fully offline (no LLM or network) and covers the trust-critical deterministic
logic: sensitive-signal scrubbing (guardrails), junk-link filtering and the SSRF guard (grounding),
defensive normalisation of model output, input validation, and retry routing.
