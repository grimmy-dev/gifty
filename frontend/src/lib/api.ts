// Typed client for the backend: plain JSON calls plus the SSE-over-POST streams.
import type {
  BatchRun,
  BatchSummary,
  Recommendation,
  RunItem,
  RunRequest,
  StreamEvent,
} from "@/lib/types"

// Backend base URL; overridable per-env via VITE_API_BASE, else local default.
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000"

interface ErrorEnvelope {
  error?: { code?: string; message?: string }
}

// Turn a non-2xx response into a thrown Error, preferring the backend's message.
async function fail(res: Response): Promise<never> {
  let message = `Request failed (${res.status})`
  try {
    const body = (await res.json()) as ErrorEnvelope
    if (body.error?.message) message = body.error.message
  } catch {
    // non-JSON error body; keep the status-based message
  }
  throw new Error(message)
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) await fail(res)
  return res.json() as Promise<T>
}

// Per-contact review acts on an item id; batch reads act on a run id.
export const reviewItem = (
  itemId: string,
  action: "approve" | "reject",
  note = ""
) => postJSON<RunItem>(`/recommendations/${itemId}/${action}`, { note })

export const regenerateItem = (itemId: string, feedback = "") =>
  postJSON<RunItem>(`/recommendations/${itemId}/regenerate`, { feedback })

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) await fail(res)
  return res.json() as Promise<T>
}

export const getItem = (itemId: string) =>
  getJSON<RunItem>(`/recommendations/${itemId}`)

export const getBatch = (runId: string) => getJSON<BatchRun>(`/runs/${runId}`)

export const listBatches = (limit = 20) =>
  getJSON<BatchSummary[]>(`/runs?limit=${limit}`)

/** Stream a batched run over one SSE-over-POST connection. */
export async function* streamRuns(
  req: RunRequest,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  yield* streamSSE("/runs/stream", req, signal)
}

/** Stream a single contact regeneration with live progress. */
export async function* streamRegenerate(
  itemId: string,
  feedback: string,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  yield* streamSSE(
    `/recommendations/${itemId}/regenerate/stream`,
    { feedback },
    signal
  )
}

// EventSource only speaks GET; the backend streams over POST, so we parse the
// text/event-stream body manually from a fetch ReadableStream.
async function* streamSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) await fail(res)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = "" // Holds bytes that don't yet form a complete frame.

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      // Chunks arrive at arbitrary boundaries; accumulate then split on frames.
      buffer += decoder.decode(value, { stream: true })

      // SSE frames are separated by a blank line; drain every complete one.
      let split: number
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, split)
        buffer = buffer.slice(split + 2) // Keep the remainder for the next read.
        const parsed = parseFrame(frame)
        if (parsed) yield parsed
      }
    }
  } finally {
    reader.releaseLock()
  }
}

// Parse one SSE frame ("event:"/"data:" lines) into a typed StreamEvent.
function parseFrame(frame: string): StreamEvent | null {
  let event = "message"
  const dataLines: string[] = []
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) } as StreamEvent
  } catch {
    return null
  }
}

export type { Recommendation }
