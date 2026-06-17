import * as React from "react"

import { getBatch, listBatches } from "@/lib/api"
import { errMsg } from "@/lib/utils"
import type { BatchSummary, RunItem } from "@/lib/types"

/** Loads recent batch runs from the backend (gifty.db) for the history view. */
export function useRecent() {
  const [batches, setBatches] = React.useState<BatchSummary[]>([])
  // Start loading so the empty-state never flashes before the first fetch.
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [details, setDetails] = React.useState<Record<string, RunItem[]>>({})

  const refresh = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setBatches(await listBatches())
    } catch (e) {
      setError(errMsg(e, "Failed to load history."))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = React.useCallback(
    async (runId: string) => {
      if (details[runId]) return
      try {
        const batch = await getBatch(runId)
        setDetails((prev) => ({ ...prev, [runId]: batch.items }))
      } catch (e) {
        setError(errMsg(e, "Failed to load run."))
      }
    },
    [details]
  )

  return { batches, details, loading, error, refresh, loadDetail }
}
