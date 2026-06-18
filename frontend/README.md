# Gifty - Frontend

The review UI for Gifty. Paste or upload enriched contact data, watch the recommendation pipeline
run live, then review each contact's gifts - approve, reject, regenerate with feedback, or export
the final JSON. A dedicated detail route shows the full trace behind any recommendation.

Built with **Vite + React + TypeScript**, **Tailwind CSS v4**, and **shadcn/ui**.

---

## Features

- **Flexible input** - paste JSON, upload a `.json` file, or load bundled sample data.
- **Live roadmap** - Server-Sent Events drive a two-level progress roadmap (collapsible phase rows
  with their sub-steps) and an elapsed timer; a Stop button cancels the in-flight run, and a
  10-minute watchdog aborts a hung one.
- **Review actions** - accept, reject, or regenerate (with optional feedback) per contact; copy or
  download the final JSON.
- **Recent runs** - a history tab lists past batches loaded from the backend.
- **Detail route** - `/recommendation/:id` refetches an item and shows every gift as labelled
  key:value fields (price / confidence / risk colour-coded) plus the full trace: profile signals,
  search queries and products-considered count, per-node model / tokens / latency, and a per-model
  usage rollup.
- **Light / dark theme** - press `d` to toggle.

---

## Tech stack

Vite · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui (Radix) · lucide-react ·
managed with [`bun`](https://bun.sh/), linted with ESLint and formatted with Prettier.

---

## Prerequisites

- **[`bun`](https://bun.sh/docs/installation)**
- The **[backend](../backend/README.md)** running (default `http://localhost:8000`).

---

## Setup

```bash
cd frontend
bun install
```

### Configuration (optional)

The API base URL defaults to `http://localhost:8000`. To point elsewhere, create `.env.local`:

```bash
VITE_API_BASE=http://localhost:8000
```

The backend's `CORS_ORIGINS` must include this app's origin (`http://localhost:5173` by default).

---

## Run

```bash
bun run dev # dev server at http://localhost:5173
```

Start the backend first (see [`../backend/README.md`](../backend/README.md)), then open the dev
server and either load the sample data or paste your own contacts.

### Other scripts

| Command | Purpose |
|---------|---------|
| `bun run dev` | Start the Vite dev server |
| `bun run build` | Type-check and build for production (`dist/`) |
| `bun run preview` | Preview the production build |
| `bun run lint` | Run ESLint |
| `bun run typecheck` | Type-check without emitting |
| `bun run format` | Format with Prettier |

---

## Project structure

```
src/
  App.tsx                  routes between the main view and the detail page
  main.tsx                 app entry + theme provider
  components/
    gifty/                 app components (input, roadmap, recommendation card, detail page, …)
    ui/                    shadcn/ui primitives
    theme-provider.tsx     light/dark theme + `d` keyboard toggle
  hooks/
    use-gifty.ts           run lifecycle: streaming, review, regenerate
    use-recent.ts          recent-runs history
    use-route.ts           minimal history-based routing (no router dependency)
    use-copy.ts            copy-to-clipboard helper
  lib/
    api.ts                 backend client (fetch + SSE-over-POST parsing)
    types.ts               shared types mirroring the backend schema
    format.ts              badge colours and formatting helpers
    sample.ts              bundled sample input + request parsing
```

---

## Notes

- Routing is intentionally dependency-free: a small `useRoute` hook over the History API handles the
  single extra `/recommendation/:id` route. The Vite dev server serves `index.html` for it on direct
  load.
- All recommendation data and review state live in the backend; this app is a thin, stateless view
  over its API.
