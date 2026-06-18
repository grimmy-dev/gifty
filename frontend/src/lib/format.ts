import type { CompactGift, RiskLevel } from "@/lib/types"

// Contextual badge colors layered on the neutral theme (use with variant="outline").
const GREEN =
  "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
const AMBER =
  "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400"
const RED = "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400"

export const riskBadgeClass: Record<RiskLevel, string> = {
  low: GREEN,
  medium: AMBER,
  high: RED,
}

export const priceBadgeClass = GREEN

/** Confidence colour: green when sure, amber mid, red when shaky. */
export function confidenceBadgeClass(score: number): string {
  if (score >= 0.75) return GREEN
  if (score >= 0.5) return AMBER
  return RED
}

/** Pretty-printed JSON for a single gift (used by the per-rank copy action). */
export function giftJSON(gift: CompactGift): string {
  return JSON.stringify(gift, null, 2)
}

export function confidencePct(score: number): string {
  return `${Math.round(score * 100)}%`
}
