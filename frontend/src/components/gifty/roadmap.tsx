import * as React from "react"
import { CheckIcon, ChevronDownIcon, Loader2Icon } from "lucide-react"

import type { RoadmapPhase } from "@/hooks/use-gifty"
import { cn } from "@/lib/utils"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

// Elapsed as "1m 32s" (drops the minutes segment under a minute).
function fmtElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

// Ticks once a second while the run is active; freezes on the final value.
function ElapsedTimer({
  startedAt,
  active,
}: {
  startedAt: number | null
  active: boolean
}) {
  const [now, setNow] = React.useState(() => Date.now())
  React.useEffect(() => {
    if (!active) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [active])
  if (!startedAt) return null
  return (
    <span className="font-mono tabular-nums">{fmtElapsed(now - startedAt)}</span>
  )
}

function PhaseRow({
  phase,
  open,
  onToggle,
}: {
  phase: RoadmapPhase
  open: boolean
  onToggle: (open: boolean) => void
}) {
  return (
    <Collapsible open={open} onOpenChange={onToggle}>
      <CollapsibleTrigger className="group flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm">
        {phase.active ? (
          <Loader2Icon className="size-4 shrink-0 animate-spin text-primary" />
        ) : (
          <CheckIcon className="size-4 shrink-0 text-emerald-500" />
        )}
        <span className={cn("font-medium", phase.active && "text-primary")}>
          {phase.label}
        </span>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {phase.steps.length} step{phase.steps.length === 1 ? "" : "s"}
        </span>
        <ChevronDownIcon
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
        <ol className="flex flex-col gap-1.5 px-4 pb-3 pl-10 font-mono text-[0.8rem]">
          {phase.steps.map((step, i) => {
            // Only the final step of the active phase is the live sub-step.
            const live = phase.active && i === phase.steps.length - 1
            return (
              <li key={step.id} className="flex gap-2 leading-relaxed">
                <span
                  className={cn(
                    "shrink-0 select-none",
                    live ? "text-primary" : "text-muted-foreground/50"
                  )}
                >
                  ›
                </span>
                <span className="min-w-0">
                  {step.contact && (
                    <span className="mr-1.5 rounded bg-foreground/10 px-1.5 py-0.5 text-[0.7rem] font-medium">
                      {step.contact}
                    </span>
                  )}
                  <span
                    className={cn(
                      live ? "text-foreground" : "text-muted-foreground"
                    )}
                  >
                    {step.detail}
                  </span>
                </span>
              </li>
            )
          })}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface RoadmapProps {
  phases: RoadmapPhase[]
  active: boolean
  startedAt: number | null
}

/** Two-level run roadmap: collapsible phase rows with their live sub-steps. */
export function Roadmap({ phases, active, startedAt }: RoadmapProps) {
  // User can collapse/expand any row; default follows whether the phase is active.
  // Keyed by the row's unique id (a phase can recur, so its name isn't unique).
  const [overrides, setOverrides] = React.useState<Record<number, boolean>>({})

  return (
    <div className="w-full animate-in overflow-hidden rounded-xl bg-muted/40 ring-1 ring-foreground/10 duration-300 fade-in slide-in-from-bottom-2">
      <div className="flex items-center gap-2 border-b bg-muted/60 px-4 py-2.5 text-sm font-medium">
        {active ? (
          <>
            <Loader2Icon className="size-4 animate-spin text-primary" />
            <span>Working through the roadmap…</span>
          </>
        ) : (
          <>
            <span className="size-2 rounded-full bg-emerald-500" aria-hidden />
            <span>Run complete</span>
          </>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          <ElapsedTimer startedAt={startedAt} active={active} />
        </span>
      </div>
      <div className="divide-y divide-border/60">
        {phases.map((phase) => (
          <PhaseRow
            key={phase.id}
            phase={phase}
            open={overrides[phase.id] ?? phase.active}
            onToggle={(o) => setOverrides((prev) => ({ ...prev, [phase.id]: o }))}
          />
        ))}
      </div>
    </div>
  )
}
