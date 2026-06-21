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
  CompactRecommendation,
  ReviewStatus,
  RunItem,
  CompactItem,
  StreamEvent,
} from "@/lib/types"

export type RunPhase = "streaming" | "ready" | "error"

export interface ContactRun {
  name: string
  itemId?: string
  phase: RunPhase
  recommendation?: CompactRecommendation
  // Locally chosen review outcome (drives the collapsed card state).
  action?: ReviewStatus
  error?: string
}

/** Map a persisted item (history / detail view) into a card-ready run. */
export function runFromItem(item: RunItem | CompactItem): ContactRun {
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

// One emitted work step within a phase.
export interface RoadmapStep {
  id: number
  contact: string | null
  detail: string
}

// A phase row in the roadmap, holding the steps that ran under it. `id` is unique
// per occurrence so a revisited phase (broaden → validate again) and each contact
// get their own row instead of merging back into an earlier one.
export interface RoadmapPhase {
  id: number
  phase: string
  label: string
  steps: RoadmapStep[]
  active: boolean
}

// Hard ceiling for one run before the watchdog aborts it (mirrors the backend
// run_timeout). A stuck provider can't pin the UI past this.
const RUN_TIMEOUT_MS = 10 * 60 * 1000

// Human labels for the backend phase ids (graph/state.py step phases).
const PHASE_LABELS: Record<string, string> = {
  analyze: "Analyzing profiles",
  search: "Searching for gifts",
  validate: "Validating products",
  broaden: "Broadening the search",
  recommend: "Ranking & writing notes",
  error: "Error",
}

type ResultData = Extract<StreamEvent, { event: "result" }>["data"]

/** Recover the compact Recommendation from a result frame, dropping the envelope. */
function recOf(data: ResultData): CompactRecommendation {
  const { run_id, item_id, status, ...rec } = data
  void [run_id, item_id, status]
  return rec
}

/**
 * Drives a batch run: streams contacts in, tracks per-contact state, and exposes
 * review/rerun actions. Owns the SSE connection and the live phase roadmap.
 */
export function useGifty() {
  const [runs, setRuns] = React.useState<ContactRun[]>([])
  const [roadmap, setRoadmap] = React.useState<RoadmapPhase[]>([])
  const [runId, setRunId] = React.useState<string | null>(null)
  const [startedAt, setStartedAt] = React.useState<number | null>(null)
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Lets a new run (or unmount) cancel the in-flight stream; see recommend/clear.
  const abortRef = React.useRef<AbortController | null>(null)
  const watchdogRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const stepId = React.useRef(0) // Monotonic key for roadmap steps.

  // Abort the in-flight stream and mark any still-streaming contacts with the
  // given reason. The fetch abort also closes the connection, so the backend
  // run is cancelled. Used by manual cancel and the hung-run watchdog.
  const stop = React.useCallback((reason: string) => {
    if (watchdogRef.current) {
      clearTimeout(watchdogRef.current)
      watchdogRef.current = null
    }
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
    setRuns((prev) =>
      prev.map((r) =>
        r.phase === "streaming" ? { ...r, phase: "error", error: reason } : r
      )
    )
    setRoadmap((prev) => prev.map((p) => ({ ...p, active: false })))
  }, [])

  const armWatchdog = React.useCallback(() => {
    if (watchdogRef.current) clearTimeout(watchdogRef.current)
    watchdogRef.current = setTimeout(
      () => stop(`Timed out after ${RUN_TIMEOUT_MS / 60000} minutes.`),
      RUN_TIMEOUT_MS
    )
  }, [stop])

  const clearWatchdog = React.useCallback(() => {
    if (watchdogRef.current) {
      clearTimeout(watchdogRef.current)
      watchdogRef.current = null
    }
  }, [])

  // Append a step to the current (trailing) row only if it's the same phase and
  // contact; otherwise open a fresh row. This keeps a revisited phase (broaden →
  // validate again) and each contact on their own row instead of jumping back.
  const pushStep = React.useCallback(
    (phase: string, detail: string, contact: string | null) =>
      setRoadmap((prev) => {
        const step = { id: stepId.current++, contact, detail }
        const last = prev[prev.length - 1]
        const sameRow =
          last && last.phase === phase && (last.steps[0]?.contact ?? null) === contact
        const next = sameRow
          ? [...prev.slice(0, -1), { ...last, steps: [...last.steps, step] }]
          : [
              ...prev,
              {
                id: step.id,
                phase,
                label: PHASE_LABELS[phase] ?? phase,
                steps: [step],
                active: true,
              },
            ]
        return next.map((p, i) => ({ ...p, active: i === next.length - 1 }))
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

  // Drive one SSE stream into state: cancel any prior stream, arm the watchdog,
  // reset the roadmap, pump every frame through `handle`, and always tear the
  // connection down. `onError` decides what a failure means for the caller (an
  // abort is reported via the `aborted` flag, not as a real failure).
  const runStream = React.useCallback(
    async (
      source: (signal: AbortSignal) => AsyncGenerator<StreamEvent>,
      handle: (ev: StreamEvent) => void,
      onError: (e: unknown, aborted: boolean) => void | Promise<void>
    ) => {
      abortRef.current?.abort()
      const ctrl = new AbortController()
      abortRef.current = ctrl

      setRoadmap([])
      setStartedAt(Date.now())
      setIsStreaming(true)
      armWatchdog()

      try {
        for await (const ev of source(ctrl.signal)) handle(ev)
      } catch (e) {
        await onError(e, ctrl.signal.aborted)
      } finally {
        clearWatchdog()
        if (abortRef.current === ctrl) abortRef.current = null
        setIsStreaming(false)
        // Run finished: no phase is active any more.
        setRoadmap((prev) => prev.map((p) => ({ ...p, active: false })))
      }
    },
    [armWatchdog, clearWatchdog]
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

      setError(null)
      setRuns([])
      setRunId(null)

      // Each SSE frame advances one contact's state; dispatch by event type.
      await runStream(
        (signal) => streamRuns(req, signal),
        (ev) => {
          if (ev.event === "start") {
            setRunId(ev.data.run_id)
            setRuns(
              ev.data.contacts.map((name) => ({ name, phase: "streaming" }))
            )
          } else if (ev.event === "analyze") {
            pushStep(
              "analyze",
              `analyzed ${ev.data.contacts.length} profile(s)`,
              null
            )
          } else if (ev.event === "step") {
            pushStep(ev.data.phase, ev.data.detail, ev.data.contact_name)
          } else if (ev.event === "result") {
            const rec = recOf(ev.data)
            patchRun(rec.contact_name, {
              itemId: ev.data.item_id,
              phase: "ready",
              recommendation: rec,
            })
          } else if (ev.event === "error") {
            patchRun(ev.data.contact_name, {
              phase: "error",
              error: ev.data.error,
            })
            pushStep("error", ev.data.error, ev.data.contact_name)
          }
        },
        // A deliberate abort throws too; only surface real failures.
        (e, aborted) => {
          if (!aborted) setError(errMsg(e, "Stream failed."))
        }
      )
    },
    [runStream, patchRun, pushStep]
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

      await runStream(
        (signal) => streamRegenerate(itemId, feedback, signal),
        (ev) => {
          if (ev.event === "step") {
            pushStep(ev.data.phase, ev.data.detail, ev.data.contact_name)
          } else if (ev.event === "result") {
            patchRun(run.name, { phase: "ready", recommendation: recOf(ev.data) })
          } else if (ev.event === "error") {
            throw new Error(ev.data.error)
          }
        },
        async (e, aborted) => {
          // Cancelled: leave the run marked by cancel(), don't fall back.
          if (aborted) return
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
      )
    },
    [runStream, patchRun, pushStep]
  )

  // Manual stop button: abort the in-flight run and mark it cancelled.
  const cancel = React.useCallback(() => stop("Cancelled."), [stop])

  const clear = React.useCallback(() => {
    clearWatchdog()
    abortRef.current?.abort()
    abortRef.current = null
    setRuns([])
    setRoadmap([])
    setRunId(null)
    setStartedAt(null)
    setError(null)
    setIsStreaming(false)
  }, [clearWatchdog])

  // Abort the stream and clear the watchdog if the component unmounts mid-run.
  React.useEffect(
    () => () => {
      if (watchdogRef.current) clearTimeout(watchdogRef.current)
      abortRef.current?.abort()
    },
    []
  )

  // Derived view state the UI switches on: nothing yet, running, or done.
  const phase = isStreaming ? "streaming" : runs.length > 0 ? "results" : "idle"

  return {
    runs,
    roadmap,
    runId,
    startedAt,
    isStreaming,
    error,
    phase,
    recommend,
    review,
    rerun,
    cancel,
    clear,
    clearError: () => setError(null),
  }
}
