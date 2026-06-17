import * as React from "react"

import {
  regenerateItem,
  reviewItem,
  streamRegenerate,
  streamRuns,
} from "@/lib/api"
import { parseRunRequest } from "@/lib/sample"
import { errMsg } from "@/lib/utils"
import type {
  Recommendation,
  ReviewStatus,
  RunItem,
  StreamEvent,
} from "@/lib/types"

export type RunPhase = "streaming" | "ready" | "error"

export interface ContactRun {
  name: string
  itemId?: string
  phase: RunPhase
  recommendation?: Recommendation
  // Locally chosen review outcome (drives the collapsed card state).
  action?: ReviewStatus
  error?: string
}

/** Map a persisted item (history / detail view) into a card-ready run. */
export function runFromItem(item: RunItem): ContactRun {
  const data = item.data
  if (data?.error || !data?.recommended_gifts) {
    return {
      name: item.contact_name,
      itemId: item.id,
      phase: "error",
      error: data?.error ?? "No recommendation data.",
    }
  }
  const action =
    item.status === "approved" ||
    item.status === "rejected" ||
    item.status === "edited"
      ? item.status
      : undefined
  return {
    name: item.contact_name,
    itemId: item.id,
    phase: "ready",
    recommendation: data,
    action,
  }
}

export interface StreamLine {
  id: number
  contact: string | null
  label: string
  kind: "info" | "node" | "result" | "error"
}

const MAX_LOG_LINES = 200

function nodeLabel(node: string, log: Record<string, unknown>): string {
  const pretty = node.replace(/_/g, " ")
  const msg = typeof log?.message === "string" ? log.message : ""
  return msg ? `${pretty}: ${msg}` : pretty
}

type ResultData = Extract<StreamEvent, { event: "result" }>["data"]

/** Recover the Recommendation from a result frame, dropping the SSE envelope fields. */
function recOf(data: ResultData): Recommendation {
  const { run_id, item_id, status, trace, ...rec } = data
  void [run_id, item_id, status, trace]
  return rec
}

export function useGifty() {
  const [runs, setRuns] = React.useState<ContactRun[]>([])
  const [log, setLog] = React.useState<StreamLine[]>([])
  const [runId, setRunId] = React.useState<string | null>(null)
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const abortRef = React.useRef<AbortController | null>(null)
  const lineId = React.useRef(0)

  const pushLine = React.useCallback(
    (line: Omit<StreamLine, "id">) =>
      setLog((prev) => {
        const next = [...prev, { ...line, id: lineId.current++ }]
        return next.length > MAX_LOG_LINES
          ? next.slice(next.length - MAX_LOG_LINES)
          : next
      }),
    []
  )

  const patchRun = React.useCallback(
    (name: string, patch: Partial<ContactRun>) =>
      setRuns((prev) =>
        prev.map((r) => (r.name === name ? { ...r, ...patch } : r))
      ),
    []
  )

  const recommend = React.useCallback(
    async (rawJSON: string) => {
      let req
      try {
        req = parseRunRequest(rawJSON)
      } catch (e) {
        setError(errMsg(e, "Invalid JSON input."))
        return
      }

      abortRef.current?.abort()
      const ctrl = new AbortController()
      abortRef.current = ctrl

      setError(null)
      setLog([])
      setRuns([])
      setRunId(null)
      setIsStreaming(true)

      try {
        for await (const ev of streamRuns(req, ctrl.signal)) {
          if (ev.event === "start") {
            setRunId(ev.data.run_id)
            setRuns(
              ev.data.contacts.map((name) => ({ name, phase: "streaming" }))
            )
            pushLine({
              contact: null,
              label: `Starting run for ${ev.data.contacts.length} contact(s)`,
              kind: "info",
            })
          } else if (ev.event === "analyze") {
            pushLine({
              contact: null,
              label: "Profiles analyzed, extracting signals",
              kind: "info",
            })
          } else if (ev.event === "node") {
            pushLine({
              contact: ev.data.contact_name,
              label: nodeLabel(ev.data.node, ev.data.log),
              kind: "node",
            })
          } else if (ev.event === "result") {
            const rec = recOf(ev.data)
            patchRun(rec.contact_name, {
              itemId: ev.data.item_id,
              phase: "ready",
              recommendation: rec,
            })
            pushLine({
              contact: rec.contact_name,
              label: `${rec.recommended_gifts.length} gift(s) recommended`,
              kind: "result",
            })
          } else if (ev.event === "error") {
            patchRun(ev.data.contact_name, {
              phase: "error",
              error: ev.data.error,
            })
            pushLine({
              contact: ev.data.contact_name,
              label: ev.data.error,
              kind: "error",
            })
          }
        }
      } catch (e) {
        if (!ctrl.signal.aborted) {
          setError(errMsg(e, "Stream failed."))
        }
      } finally {
        if (abortRef.current === ctrl) abortRef.current = null
        setIsStreaming(false)
      }
    },
    [patchRun, pushLine]
  )

  const review = React.useCallback(
    async (run: ContactRun, action: "approve" | "reject") => {
      if (!run.itemId) return
      const status: ReviewStatus =
        action === "approve" ? "approved" : "rejected"
      patchRun(run.name, { action: status })
      try {
        await reviewItem(run.itemId, action)
      } catch (e) {
        setError(errMsg(e, "Review failed."))
        patchRun(run.name, { action: undefined })
      }
    },
    [patchRun]
  )

  const rerun = React.useCallback(
    async (run: ContactRun, feedback: string) => {
      if (!run.itemId) return
      const itemId = run.itemId
      patchRun(run.name, { phase: "streaming", action: undefined })
      pushLine({
        contact: run.name,
        label: feedback ? `Rerun: ${feedback}` : "Rerunning recommendation",
        kind: "info",
      })
      try {
        let updated: Recommendation | undefined
        for await (const ev of streamRegenerate(itemId, feedback)) {
          if (ev.event === "node") {
            pushLine({
              contact: run.name,
              label: nodeLabel(ev.data.node, ev.data.log),
              kind: "node",
            })
          } else if (ev.event === "result") {
            updated = recOf(ev.data)
          } else if (ev.event === "error") {
            throw new Error(ev.data.error)
          }
        }
        patchRun(run.name, { phase: "ready", recommendation: updated })
      } catch (e) {
        // Fall back to the non-streaming endpoint if the stream breaks.
        try {
          const item = await regenerateItem(itemId, feedback)
          patchRun(run.name, { phase: "ready", recommendation: item.data })
        } catch {
          patchRun(run.name, {
            phase: "error",
            error: errMsg(e, "Rerun failed."),
          })
        }
      }
    },
    [patchRun, pushLine]
  )

  const clear = React.useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setRuns([])
    setLog([])
    setRunId(null)
    setError(null)
    setIsStreaming(false)
  }, [])

  React.useEffect(() => () => abortRef.current?.abort(), [])

  const phase = isStreaming ? "streaming" : runs.length > 0 ? "results" : "idle"

  return {
    runs,
    log,
    runId,
    isStreaming,
    error,
    phase,
    recommend,
    review,
    rerun,
    clear,
    clearError: () => setError(null),
  }
}
