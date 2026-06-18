// Standalone /recommendation/:id page: full gift fields plus the saved trace.
import * as React from "react"
import { ArrowLeftIcon, ExternalLinkIcon, Loader2Icon } from "lucide-react"

import { getItem } from "@/lib/api"
import { navigate } from "@/hooks/use-route"
import {
  confidenceBadgeClass,
  confidencePct,
  giftJSON,
  priceBadgeClass,
  riskBadgeClass,
} from "@/lib/format"
import { cn, errMsg } from "@/lib/utils"
import type {
  ModelUsage,
  RecommendedGift,
  RunItemDetail,
  TraceEntry,
} from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { CopyButton } from "@/components/gifty/copy-button"

// Narrow an unknown trace value to a number, since trace entries are loosely typed.
function num(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined
}

/** One labelled key:value row in a gift's detail grid. */
function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  if (children === null || children === undefined || children === "")
    return null
  return (
    <div className="grid grid-cols-1 gap-0.5 sm:grid-cols-[180px_1fr] sm:gap-4">
      <dt className="text-xs font-semibold tracking-wider text-muted-foreground uppercase sm:pt-0.5">
        {label}
      </dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

function GiftDetail({ gift }: { gift: RecommendedGift }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg bg-muted/40 p-5 ring-1 ring-foreground/5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge variant={gift.rank === 1 ? "default" : "secondary"}>
            Rank {gift.rank}
          </Badge>
          {gift.rank === 1 && (
            <Badge variant="outline" className="bg-emerald-400/50 p-2">
              Top pick
            </Badge>
          )}
          <h2 className="font-heading text-lg leading-tight font-semibold">
            {gift.gift_name}
          </h2>
        </div>
        <CopyButton value={giftJSON(gift)} label="copy json" />
      </div>

      <dl className="flex flex-col gap-3">
        <Field label="Store">{gift.store}</Field>
        <Field label="Estimated price">
          <Badge
            variant="outline"
            className={cn("font-normal", priceBadgeClass)}
          >
            {gift.estimated_price}
          </Badge>
        </Field>
        <Field label="Product URL">
          {gift.product_url ? (
            <a
              href={gift.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="break-all text-primary underline-offset-4 hover:underline"
            >
              {gift.product_url}
              <ExternalLinkIcon className="mb-0.5 ml-1 inline size-3 align-text-bottom" />
            </a>
          ) : null}
        </Field>
        <Field label="Why this gift">{gift.why_this_gift}</Field>
        <Field label="Personalisation reasoning">
          {gift.personalisation_reasoning}
        </Field>
        <Field label="Personalised message">
          {gift.personalised_message ? (
            <blockquote className="border-l-2 border-primary/40 pl-3 italic">
              {gift.personalised_message}
            </blockquote>
          ) : null}
        </Field>
        <Field label="Confidence">
          <Badge
            variant="outline"
            className={cn(
              "font-normal",
              confidenceBadgeClass(gift.confidence_score)
            )}
          >
            {confidencePct(gift.confidence_score)} sure
          </Badge>
        </Field>
        <Field label="Risk level">
          <Badge
            variant="outline"
            className={cn("font-normal", riskBadgeClass[gift.risk_level])}
          >
            {gift.risk_level} risk
          </Badge>
        </Field>
        <Field label="Assumptions">
          {gift.assumptions.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {gift.assumptions.map((a, i) => (
                <li key={i} className="flex gap-1.5">
                  <span aria-hidden className="text-muted-foreground/60">
                    •
                  </span>
                  {a}
                </li>
              ))}
            </ul>
          ) : null}
        </Field>
      </dl>
    </div>
  )
}

function TraceRow({ entry }: { entry: TraceEntry }) {
  const node = (entry.node ?? "step").replace(/_/g, " ")
  const model = typeof entry.model === "string" ? entry.model : null
  const ms = num(entry.ms)
  const tokensIn = num(entry.tokens_in)
  const tokensOut = num(entry.tokens_out)
  const tokens =
    tokensIn !== undefined || tokensOut !== undefined
      ? `${tokensIn ?? 0} in / ${tokensOut ?? 0} out`
      : null
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2 text-sm">
      <span className="font-medium">{node}</span>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-muted-foreground">
        {model && <span>{model}</span>}
        {tokens && <span>{tokens}</span>}
        {ms !== undefined && <span className="tabular-nums">{ms} ms</span>}
      </div>
    </div>
  )
}

/** Full detail for one recommendation: every gift as labelled key:value fields,
 *  plus the persisted trace (profile signals, search, per-node model/tokens/ms). */
export function DetailPage({ itemId }: { itemId: string }) {
  const [item, setItem] = React.useState<RunItemDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    // `active` guards against a setState after unmount if the fetch resolves late.
    let active = true
    getItem(itemId)
      .then((res) => active && setItem(res))
      .catch(
        (e) => active && setError(errMsg(e, "Failed to load recommendation."))
      )
    return () => {
      active = false
    }
  }, [itemId])

  return (
    <div className="mx-auto flex min-h-svh w-full max-w-4xl flex-col gap-8 px-6 py-16 sm:py-20">
      <Button
        variant="ghost"
        className="-ml-2 w-fit text-muted-foreground"
        onClick={() => navigate("/")}
      >
        <ArrowLeftIcon />
        Back
      </Button>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!item && !error && (
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2Icon className="size-4 animate-spin" />
          Loading recommendation…
        </div>
      )}

      {item && <DetailBody item={item} />}
    </div>
  )
}

function UsageRow({ row, total }: { row: ModelUsage; total?: boolean }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2 text-sm">
      <span className={cn("font-medium", total && "font-semibold")}>
        {row.model}
      </span>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-muted-foreground">
        <span className="tabular-nums">{row.calls} calls</span>
        <span className="tabular-nums">
          {row.tokens_in} in / {row.tokens_out} out
        </span>
        <span className="tabular-nums">{row.ms} ms</span>
      </div>
    </div>
  )
}

function DetailBody({ item }: { item: RunItemDetail }) {
  const data = item.data
  const gifts = [...(data.recommended_gifts ?? [])].sort(
    (a, b) => a.rank - b.rank
  )
  const signals = data.profile_signals
  const search = data.search_trace
  const trace = data.trace ?? []
  const usage = item.usage
  // Sum each node's latency for the pipeline header total.
  const totalMs = trace.reduce((sum, e) => sum + (num(e.ms) ?? 0), 0)
  const note = data.human_review?.note

  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-heading text-3xl font-bold">
            {item.contact_name}
          </h1>
          <Badge variant="secondary">{item.status.replace(/_/g, " ")}</Badge>
        </div>
        <span className="font-mono text-xs text-muted-foreground">
          run {item.run_id} · item {item.id}
        </span>
      </div>

      {data.error && <p className="text-sm text-destructive">{data.error}</p>}
      {note && (
        <p className="rounded-lg bg-muted/60 px-4 py-3 text-sm text-muted-foreground">
          {note}
        </p>
      )}
      {data.ranking_reason && (
        <p className="text-sm text-muted-foreground italic">
          {data.ranking_reason}
        </p>
      )}

      {gifts.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="font-heading text-lg font-semibold">
            Recommended gifts ({gifts.length})
          </h2>
          {gifts.map((gift) => (
            <GiftDetail key={gift.rank} gift={gift} />
          ))}
        </section>
      )}

      <section className="flex flex-col gap-5 rounded-xl bg-muted/30 p-5 ring-1 ring-foreground/5">
        <h2 className="font-heading text-lg font-semibold">Trace</h2>

        {signals && (
          <div className="flex flex-col gap-3">
            <SignalList title="Strong signals" items={signals.strong_signals} />
            <SignalList title="Weak signals" items={signals.weak_signals} />
            <SignalList
              title="Signals avoided"
              items={signals.signals_to_avoid}
            />
          </div>
        )}

        {search && (
          <>
            <Separator />
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Search · {search.products_considered_count} products considered
              </h3>
              <ul className="flex flex-col gap-1 font-mono text-xs text-muted-foreground">
                {search.queries_used.map((q, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span aria-hidden className="text-muted-foreground/60">
                      ›
                    </span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}

        {trace.length > 0 && (
          <>
            <Separator />
            <div className="flex flex-col gap-1">
              <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Pipeline · {totalMs} ms total
              </h3>
              <div className="divide-y divide-border/60">
                {trace.map((entry, i) => (
                  <TraceRow key={i} entry={entry} />
                ))}
              </div>
            </div>
          </>
        )}

        {usage.by_model.length > 0 && (
          <>
            <Separator />
            <div className="flex flex-col gap-1">
              <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Usage by model
              </h3>
              <div className="divide-y divide-border/60">
                {usage.by_model.map((row) => (
                  <UsageRow key={row.model} row={row} />
                ))}
                <UsageRow row={usage.totals} total />
              </div>
            </div>
          </>
        )}
      </section>
    </>
  )
}

function SignalList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
        {title}
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {items.map((s, i) => (
          <Badge key={i} variant="secondary" className="font-normal">
            {s}
          </Badge>
        ))}
      </div>
    </div>
  )
}
