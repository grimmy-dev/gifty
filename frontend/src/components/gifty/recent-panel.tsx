import * as React from "react"
import {
  ChevronDownIcon,
  InboxIcon,
  Loader2Icon,
  RefreshCwIcon,
} from "lucide-react"

import { useRecent } from "@/hooks/use-recent"
import type { ContactRun } from "@/hooks/use-gifty"
import type { RunItem } from "@/lib/types"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { RecommendationCard } from "@/components/gifty/recommendation-card"

function formatDate(ts: string): string {
  // SQLite CURRENT_TIMESTAMP is UTC without a zone marker.
  const date = new Date(ts.replace(" ", "T") + "Z")
  return Number.isNaN(date.getTime())
    ? ts
    : date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
}

function toRun(item: RunItem): ContactRun {
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

function BatchGroup({
  runId,
  createdAt,
  count,
  items,
  onOpen,
}: {
  runId: string
  createdAt: string
  count: number
  items?: RunItem[]
  onOpen: () => void
}) {
  return (
    <Collapsible
      className="rounded-xl ring-1 ring-foreground/10"
      onOpenChange={(open) => open && onOpen()}
    >
      <CollapsibleTrigger className="group flex w-full items-center gap-3 px-4 py-3 text-left">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="font-mono text-xs text-muted-foreground">
            run {runId}
          </span>
          <span className="text-sm font-medium">
            {count} contact{count === 1 ? "" : "s"}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {formatDate(createdAt)}
        </span>
        <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
        <div className="flex flex-col gap-4 border-t p-4">
          {items ? (
            items.map((item) => (
              <RecommendationCard key={item.id} run={toRun(item)} readOnly />
            ))
          ) : (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              Loading run…
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function RecentPanel() {
  const { batches, details, loading, error, refresh, loadDetail } = useRecent()

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  if (loading && batches.length === 0) {
    return (
      <div
        role="status"
        className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"
      >
        <Loader2Icon className="size-4 animate-spin" />
        Loading recent runs…
      </div>
    )
  }

  if (batches.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div
          role="status"
          className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed py-16 text-center"
        >
          <InboxIcon className="size-8 text-muted-foreground" />
          <p className="text-sm font-medium">No recommendations yet</p>
          <p className="max-w-xs text-xs text-muted-foreground">
            Runs you generate are saved to the database and show up here.
          </p>
          <Button variant="outline" className="mt-2" onClick={() => refresh()}>
            <RefreshCwIcon />
            Refresh
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg font-semibold">Recent runs</h2>
        <Button
          variant="ghost"
          onClick={() => refresh()}
          disabled={loading}
          aria-label="Refresh history"
        >
          <RefreshCwIcon className={cn(loading && "animate-spin")} />
          Refresh
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {batches.map((batch) => (
        <BatchGroup
          key={batch.run_id}
          runId={batch.run_id}
          createdAt={batch.created_at}
          count={batch.contacts.length}
          items={details[batch.run_id]}
          onOpen={() => loadDetail(batch.run_id)}
        />
      ))}
    </div>
  )
}
