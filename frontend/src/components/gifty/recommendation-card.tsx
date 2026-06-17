import * as React from "react"
import {
  ArrowRightIcon,
  CheckIcon,
  ChevronDownIcon,
  DownloadIcon,
  Loader2Icon,
  RotateCwIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react"

import type { ContactRun } from "@/hooks/use-gifty"
import { navigate } from "@/hooks/use-route"
import type { Recommendation, ReviewStatus } from "@/lib/types"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { CopyButton } from "@/components/gifty/copy-button"
import { GiftMini, GiftPrimary } from "@/components/gifty/gift-cards"

const actionBadge: Record<ReviewStatus, { label: string; variant: "secondary" | "destructive" | "default" }> = {
  approved: { label: "Accepted", variant: "default" },
  rejected: { label: "Rejected", variant: "destructive" },
  edited: { label: "Edited", variant: "secondary" },
  pending_review: { label: "Pending", variant: "secondary" },
  failed: { label: "Failed", variant: "destructive" },
}

function sortedGifts(rec: Recommendation) {
  return [...rec.recommended_gifts].sort((a, b) => a.rank - b.rank)
}

function downloadJSON(rec: Recommendation) {
  const blob = new Blob([JSON.stringify(rec, null, 2)], {
    type: "application/json",
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `gifty-${rec.contact_name.replace(/\s+/g, "-").toLowerCase()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

interface RecommendationCardProps {
  run: ContactRun
  readOnly?: boolean
  onReview?: (run: ContactRun, action: "approve" | "reject") => void
  onRerun?: (run: ContactRun, feedback: string) => void
}

export const RecommendationCard = React.memo(function RecommendationCard({
  run,
  readOnly = false,
  onReview,
  onRerun,
}: RecommendationCardProps) {
  const rec = run.recommendation
  const busy = run.phase === "streaming"
  const [open, setOpen] = React.useState(true)
  const [showFeedback, setShowFeedback] = React.useState(false)
  const [feedback, setFeedback] = React.useState("")

  // Collapse to the summary row once a review outcome is chosen.
  React.useEffect(() => {
    if (run.action) setOpen(false)
  }, [run.action])

  if (run.phase === "error") {
    return (
      <Card className="border-destructive/40">
        <CardHeader className="flex flex-row items-center gap-2.5">
          <TriangleAlertIcon className="size-5 shrink-0 text-destructive" />
          <div className="flex flex-col">
            <span className="font-medium">{run.name}</span>
            <span className="text-sm text-destructive">{run.error}</span>
          </div>
        </CardHeader>
      </Card>
    )
  }

  if (!rec) return null
  const gifts = sortedGifts(rec)
  const [primary, ...alternates] = gifts
  const note = rec.human_review.note
  const chosen = run.action ? actionBadge[run.action] : null

  // Reflect the chosen review outcome in exported JSON (not the stale pending_review).
  const exportRec: Recommendation = run.action
    ? { ...rec, human_review: { ...rec.human_review, status: run.action } }
    : rec
  const exportJSON = JSON.stringify(exportRec, null, 2)

  function submitRerun() {
    onRerun?.(run, feedback.trim())
    setShowFeedback(false)
    setFeedback("")
  }

  return (
    <Card
      className={cn(
        "animate-in gap-0 py-0 transition-shadow duration-300 fade-in slide-in-from-bottom-2 [--card-spacing:--spacing(5)]",
        chosen?.variant === "default" && "ring-primary/30"
      )}
    >
      <Collapsible open={open} onOpenChange={setOpen}>
        <CardHeader className="flex flex-row items-center gap-3 py-4">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-heading text-lg font-semibold">
                {rec.contact_name}
              </span>
              {busy && (
                <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
              )}
              {chosen && (
                <Badge variant={chosen.variant} className="h-6 px-2.5 text-sm">
                  {chosen.label}
                </Badge>
              )}
            </div>
            {primary && (
              <span className="truncate text-sm text-muted-foreground">
                {open
                  ? `${gifts.length} gift options ready for review`
                  : primary.gift_name}
              </span>
            )}
          </div>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              aria-label={open ? "Collapse" : "Expand"}
            >
              <ChevronDownIcon
                className={cn(
                  "size-5 transition-transform duration-200",
                  open && "rotate-180"
                )}
              />
            </Button>
          </CollapsibleTrigger>
        </CardHeader>

        <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
          <CardContent className="flex flex-col gap-5 pb-5">
            {note && (
              <p className="rounded-lg bg-muted/60 px-4 py-3 text-sm text-muted-foreground">
                {note}
              </p>
            )}
            {primary && (
              <section className="flex flex-col gap-2.5">
                <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  Top pick
                </h3>
                <GiftPrimary gift={primary} />
              </section>
            )}
            {alternates.length > 0 && (
              <section className="flex flex-col gap-2.5">
                <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  Other options
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  {alternates.map((g) => (
                    <GiftMini key={g.rank} gift={g} />
                  ))}
                </div>
              </section>
            )}
            {run.itemId && (
              <Button
                variant="ghost"
                size="sm"
                className="-ml-2 w-fit text-muted-foreground"
                onClick={() => navigate(`/recommendation/${run.itemId}`)}
              >
                View more
                <ArrowRightIcon />
              </Button>
            )}
          </CardContent>

          {readOnly || chosen ? (
            <CardFooter className="items-center justify-between gap-2">
              {chosen && !readOnly ? (
                <span className="text-sm text-muted-foreground">
                  You {chosen.label.toLowerCase()} this recommendation.
                </span>
              ) : (
                <span />
              )}
              <div className="flex items-center gap-2">
                <CopyButton value={exportJSON} label="copy" />
                <Button variant="outline" onClick={() => downloadJSON(exportRec)}>
                  <DownloadIcon />
                  json
                </Button>
              </div>
            </CardFooter>
          ) : showFeedback ? (
            <CardFooter className="flex-col items-stretch gap-2">
              <Textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Optional: what should change on rerun?"
                rows={2}
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setShowFeedback(false)}>
                  Cancel
                </Button>
                <Button onClick={submitRerun}>
                  <RotateCwIcon />
                  Rerun
                </Button>
              </div>
            </CardFooter>
          ) : (
            <CardFooter className="gap-2">
              <Button
                variant="default"
                disabled={busy}
                onClick={() => onReview?.(run, "approve")}
              >
                <CheckIcon />
                Accept
              </Button>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => setShowFeedback(true)}
              >
                <RotateCwIcon />
                Rerun
              </Button>
              <Separator orientation="vertical" className="h-5" />
              <Button
                variant="destructive"
                disabled={busy}
                onClick={() => onReview?.(run, "reject")}
              >
                <XIcon />
                Reject
              </Button>
            </CardFooter>
          )}
        </CollapsibleContent>
      </Collapsible>
    </Card>
  )
})
