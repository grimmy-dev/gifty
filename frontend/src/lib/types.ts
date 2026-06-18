// Mirrors the backend Pydantic I/O schemas (backend/utils/models.py).

export type RiskLevel = "low" | "medium" | "high"
export type ReviewStatus =
  | "pending_review"
  | "approved"
  | "rejected"
  | "edited"
  | "failed"
export type ReviewAction = "approve" | "reject" | "edit" | "regenerate"

export interface Experience {
  title: string
  company: string
  description: string
}

export interface LinkedInProfile {
  headline: string
  about: string
  experience: Experience[]
  recent_posts: string[]
  recent_comments: string[]
  engaged_topics: string[]
}

export interface RelationshipContext {
  relationship_type: string
  last_interaction: string
  business_goal: string
}

export interface GiftContext {
  occasion: string
  budget_min: number
  budget_max: number
  currency: string
  country: string
}

export interface Contact {
  name: string
  role: string
  company: string
  location: string
  linkedin_profile: LinkedInProfile
  relationship_context: RelationshipContext
  gift_context: GiftContext
}

export interface RunRequest {
  contacts: Contact[]
}

export interface ProfileSignals {
  strong_signals: string[]
  weak_signals: string[]
  signals_to_avoid: string[]
}

export interface SearchTrace {
  queries_used: string[]
  products_considered_count: number
}

export interface RecommendedGift {
  rank: number
  gift_name: string
  product_url: string
  store: string
  estimated_price: string
  why_this_gift: string
  personalisation_reasoning: string
  personalised_message: string
  confidence_score: number
  risk_level: RiskLevel
  assumptions: string[]
}

export interface HumanReview {
  status: ReviewStatus
  available_actions: ReviewAction[]
  note: string
}

export interface Recommendation {
  contact_name: string
  profile_signals: ProfileSignals
  search_trace: SearchTrace
  recommended_gifts: RecommendedGift[]
  ranking_reason: string
  human_review: HumanReview
}

// Card-sized gift: detail fields present only on the top pick (rank 1).
export interface CompactGift {
  rank: number
  gift_name: string
  product_url: string
  store: string
  estimated_price: string
  why_this_gift: string
  confidence_score: number
  risk_level: RiskLevel
  personalisation_reasoning?: string | null
  personalised_message?: string | null
  assumptions?: string[]
}

// Result schema shipped to cards: no inputs/trace, gifts trimmed to CompactGift.
export interface CompactRecommendation {
  contact_name: string
  profile_signals: ProfileSignals
  search_trace: SearchTrace
  recommended_gifts: CompactGift[]
  ranking_reason: string
  human_review: HumanReview
}

// Per-model token/latency rollup shown on the detail page.
export interface ModelUsage {
  model: string
  calls: number
  tokens_in: number
  tokens_out: number
  ms: number
}

export interface Usage {
  by_model: ModelUsage[]
  totals: ModelUsage
}

// One persisted contact recommendation (an item within a batch run).
export interface RunItem {
  id: string
  run_id: string
  contact_name: string
  status: ReviewStatus
  created_at: string
  data: Recommendation & {
    trace?: TraceEntry[]
    inputs?: unknown
    error?: string
  }
}

// Full item plus the derived per-model usage rollup (detail page).
export interface RunItemDetail extends RunItem {
  usage: Usage
}

// One persisted item with its result compacted for card rendering.
export interface CompactItem {
  id: string
  run_id: string
  contact_name: string
  status: ReviewStatus
  created_at: string
  data: CompactRecommendation & { error?: string }
}

export interface CompactBatchRun {
  run_id: string
  created_at: string
  items: CompactItem[]
}

export interface ContactStatus {
  item_id: string
  contact_name: string
  status: ReviewStatus
}

// Lightweight recent-batch listing for the history view.
export interface BatchSummary {
  run_id: string
  created_at: string
  contacts: ContactStatus[]
}

// SSE stream frames emitted by POST /runs/stream.
export interface TraceEntry {
  node?: string
  [key: string]: unknown
}

export type StreamEvent =
  | { event: "start"; data: { run_id: string; contacts: string[] } }
  | { event: "analyze"; data: { run_id: string; contacts: string[] } }
  | {
      event: "step"
      data: { contact_name: string; phase: string; detail: string }
    }
  | {
      event: "result"
      data: {
        run_id: string
        item_id: string
        contact_name: string
        status: ReviewStatus
      } & CompactRecommendation
    }
  | { event: "error"; data: { contact_name: string; error: string } }
