# Design decisions

What I picked, and how it differs from the usual approach.

## Native SDKs, not LangChain

Call the Anthropic and Google SDKs directly; `llm/client.py` is a small factory for the
provider toggle and fast/smart tiers. All I need is "prompt in, typed object out", a few dozen
lines per provider. LangChain's wrapper buys portability I don't use and adds a big dependency
tree and indirection to debug. LangGraph nodes are plain functions, so they never needed
LangChain LLM objects. SQLite is stdlib. Fewer deps, clearer traces.

## Review as REST rows, not LangGraph `interrupt()`

The graph runs to completion and saves a plain DB row. Review (approve/reject/regenerate) is
separate REST endpoints that mutate rows.

`interrupt()` suspends the graph in a live checkpointer tied to the runtime. Problems with that
here:

- **Durability.** A restart mid-review makes resume fragile. Rows survive restarts; review can
  happen days later.
- **Decoupling.** Graph stays a pure function (contacts to recommendations): easy to test and
  replay. Review is a data concern, kept apart.
- **Scale.** N pending reviews is N rows, not N suspended graphs in memory.
- **REST fit.** `interrupt()` forces threading `thread_id` and `Command` objects through HTTP.
- **No loss.** Its one perk, resume-to-skip-recompute, is useless here: approve/reject
  recompute nothing, and regenerate re-runs the cheap graph on purpose. Each row stores the
  graph inputs, so regenerate needs nothing from the original request.

## Recommend-only: no edit action

The product recommends; it does not let reviewers hand-edit gifts. Approve, reject, and
regenerate cover the review loop. An edit endpoint was dropped (along with its unused frontend
client) rather than ship a half-wired action. Less surface, one clear path: if a pick is wrong,
regenerate with feedback.

## Regenerate is per-contact, not per-batch

Regenerate re-runs one contact at a time, never a whole batch. Same reason as the sequential UI
path: each run is LLM calls and tokens, and on a free tier that cost is the binding constraint.
A reviewer rejects a specific contact's picks, so regenerating just that one is both the natural
action and the cheap one. No batch-wide re-run that burns calls on contacts already approved.

## Search then validate; the model never names products

Real URLs come from web search. Dead links dropped, model judges relevance/budget/country,
only survivors get ranked, and the model must reuse their exact URLs. Models hallucinate
products and links confidently, so grounding is enforced in code, not a prompt. This is the
whole trust property of the app.

## Deterministic safety guard behind the prompt

The prompt says don't infer religion, politics, health, ethnicity, gender, or family status. A
substring filter then strips any signal mentioning those terms regardless of model output.
Prompts are guidance, not guarantees; for a rule that matters, a cheap backstop catches the
slips.

## Sequential streaming on the UI path

`POST /runs` runs contacts concurrently (semaphore-bounded). The live path `POST /runs/stream`
does one contact at a time over a single connection. I'm on a free tier with Gemini models,
where rate limits and token cost bind, not latency. One graph at a time keeps calls under the
limit and spend predictable. The concurrent path stays for when throughput matters more.

## SSE over POST, parsed by hand

`EventSource` only does GET and can't send a body, but a run posts a batch of contacts. So the
stream is read straight off the fetch `ReadableStream`, splitting frames on blank lines. Keeps
the payload in the request body where it belongs.

## Typed output via tool use / response schema

Results come back typed: a forced tool call whose schema is the Pydantic model (Claude), or a
response schema (Gemini), validated back into the model. The provider enforces shape at
generation time, killing a class of parse-and-repair bugs. One Pydantic model is the source of
truth for generation, validation, and the API.

## Raw ASGI error middleware

The 500 envelope is raw ASGI inside the CORS layer, not `BaseHTTPMiddleware`. The latter
buffers the response and breaks SSE. Raw ASGI passes bytes through, and sitting inside CORS
means 500s still carry CORS headers.

## SQLite, not a managed DB

One SQLite file in WAL mode, sync calls in a threadpool. Zero setup, stdlib, plenty for this
scope. Isolated behind `utils/db.py`, so Postgres later is a contained swap.

## No router on the frontend

A small `useRoute` hook over the History API handles the one extra route
(`/recommendation/:id`). A router library is too much surface for two views.

## Narrated process, not model reasoning

The progress stream narrates the real pipeline: queries run, links checked and dropped,
candidates weighed, and a one-line reason for the final order. It does not stream
chain-of-thought. The calls use forced tool output, so there are no reasoning tokens, and
a free tier rules out paying for extended thinking. Every streamed line maps to work that
happened, which reads like reasoning without inventing any.

## Live sub-steps via LangGraph's custom stream writer

Nodes emit each sub-step through `get_stream_writer()`, drained over
`stream_mode=["custom","values"]`. The alternative, atomic nodes plus a frontend replay
of sub-steps after each node finishes, invents timing the backend never saw. One node per
query was rejected too: it distorts the pipeline to buy granularity the writer already
gives. A step appears when its query runs or its link is checked.

## Two-tier read payloads; inputs stay server-side

Cards get a compact shape (rank 1 full, alternates trimmed, no trace); the detail page
gets everything plus usage. The stored graph `inputs` (signals, queries, prompt material)
no longer reach the browser; they exist only to make regenerate self-contained. Sending
the full row to a card was waste and a small leak of internal prompt data.

## Usage derived from the trace, not a usage table

Per-model call counts and token totals are computed from the trace already stored on each
item (`GROUP BY model`), shown on the detail page. A usage table only pays off
for cross-item SQL rollups, which aren't needed. The data is already persisted, so a
read-time fold adds no schema or migration.

## Two-channel logging behind one flag

Detailed logs go to a rotating file (`logs/gifty.log`); the console shows only request
lifecycle (received / processing / completed / failed, with a log pointer) and errors. A
global `DEBUG` flag mirrors the full file detail to the terminal. Rotation caps the file
so it neither grows unbounded nor disappears.
