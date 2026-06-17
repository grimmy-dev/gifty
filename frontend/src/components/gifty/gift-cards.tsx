import * as React from "react"
import { ExternalLinkIcon, QuoteIcon } from "lucide-react"

import {
  confidenceBadgeClass,
  confidencePct,
  giftJSON,
  priceBadgeClass,
  riskBadgeClass,
} from "@/lib/format"
import type { RecommendedGift } from "@/lib/types"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { CopyButton } from "@/components/gifty/copy-button"

const badgeSize = "h-6 px-2.5 text-[0.8rem]"

function GiftMeta({ gift }: { gift: RecommendedGift }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="outline" className={cn(badgeSize, priceBadgeClass)}>
        {gift.estimated_price}
      </Badge>
      {gift.store && (
        <Badge variant="secondary" className={badgeSize}>
          {gift.store}
        </Badge>
      )}
      <Badge
        variant="outline"
        className={cn(badgeSize, riskBadgeClass[gift.risk_level])}
      >
        {gift.risk_level} risk
      </Badge>
      <Badge
        variant="outline"
        className={cn(badgeSize, confidenceBadgeClass(gift.confidence_score))}
      >
        {confidencePct(gift.confidence_score)} sure
      </Badge>
    </div>
  )
}

function ProductLink({ gift }: { gift: RecommendedGift }) {
  if (!gift.product_url) return null
  return (
    <a
      href={gift.product_url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex w-fit items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline"
    >
      View product
      <ExternalLinkIcon className="size-3" />
    </a>
  )
}

/** Rank-1 detail block: full info, personalised message, copy of rank-1 JSON. */
export const GiftPrimary = React.memo(function GiftPrimary({
  gift,
}: {
  gift: RecommendedGift
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4 ring-1 ring-foreground/5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Badge variant="default">Rank 1</Badge>
            <h3 className="font-heading text-lg leading-tight font-semibold">
              {gift.gift_name}
            </h3>
          </div>
          <p className="text-sm text-muted-foreground">{gift.why_this_gift}</p>
        </div>
        <CopyButton value={giftJSON(gift)} label="copy json" />
      </div>

      <GiftMeta gift={gift} />
      <ProductLink gift={gift} />

      {gift.personalisation_reasoning && (
        <p className="text-sm text-muted-foreground">
          {gift.personalisation_reasoning}
        </p>
      )}

      {gift.personalised_message && (
        <figure className="flex gap-2 rounded-md border-l-2 border-primary/40 bg-background/60 p-3">
          <QuoteIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <blockquote className="text-sm italic">
            {gift.personalised_message}
          </blockquote>
        </figure>
      )}

      {gift.assumptions.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
          {gift.assumptions.map((a, i) => (
            <li key={i} className="flex gap-1.5">
              <span aria-hidden className="text-muted-foreground/60">
                •
              </span>
              {a}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
})

/** Compact alternate (rank 2 / 3): no personalised message. */
export const GiftMini = React.memo(function GiftMini({
  gift,
}: {
  gift: RecommendedGift
}) {
  return (
    <div
      className={cn(
        "flex h-full flex-col gap-2 rounded-lg border p-3.5",
        "transition-colors hover:border-foreground/20"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <Badge variant="secondary">Rank {gift.rank}</Badge>
        <span className="text-xs text-muted-foreground">
          {confidencePct(gift.confidence_score)} sure
        </span>
      </div>
      <h4 className="leading-snug font-medium">{gift.gift_name}</h4>
      <p className="line-clamp-3 text-xs text-muted-foreground">
        {gift.why_this_gift}
      </p>
      <div className="mt-auto flex flex-col gap-2 pt-1">
        <GiftMeta gift={gift} />
        <ProductLink gift={gift} />
      </div>
    </div>
  )
})
