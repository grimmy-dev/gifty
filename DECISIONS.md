# Design decisions

What I picked, and how it differs from the usual approach.

## Native SDKs, not LangChain

Call the Anthropic and Google SDKs directly; `llm/client.py` is a small factory for the
provider toggle and fast/smart tiers. All I need is "prompt in, typed object out", a few dozen
lines per provider. LangChain's wrapper buys portability I don't use and adds a big dependency
tree and indirection to debug. LangGraph nodes are plain functions, so they never needed
LangChain LLM objects. SQLite is stdlib. Fewer deps, clearer traces.

## Review as REST rows, not LangGraph `interrupt()`

The graph runs to completion and saves a plain DB row. Review (approve/reject/edit/regenerate)
is separate REST endpoints that mutate rows.

`interrupt()` suspends the graph in a live checkpointer tied to the runtime. Problems with that
here:

- **Durability.** A restart mid-review makes resume fragile. Rows survive restarts; review can
  happen days later.
- **Decoupling.** Graph stays a pure function (contacts to recommendations): easy to test and
  replay. Review is a data concern, kept apart.
- **Scale.** N pending reviews is N rows, not N suspended graphs in memory.
- **REST fit.** `interrupt()` forces threading `thread_id` and `Command` objects through HTTP.
- **No loss.** Its one perk, resume-to-skip-recompute, is useless here: approve/reject/edit
  recompute nothing, and regenerate re-runs the cheap graph on purpose. Each row stores the
  graph inputs, so regenerate needs nothing from the original request.

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
