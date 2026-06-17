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
  human_review: HumanReview
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

export interface BatchRun {
  run_id: string
  created_at: string
  items: RunItem[]
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
      event: "node"
      data: { contact_name: string; node: string; log: TraceEntry }
    }
  | {
      event: "result"
      data: {
        run_id: string
        item_id: string
        contact_name: string
        status: ReviewStatus
      } & Recommendation & { trace?: TraceEntry[] }
    }
  | { event: "error"; data: { contact_name: string; error: string } }
