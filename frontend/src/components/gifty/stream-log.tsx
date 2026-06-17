import * as React from "react"
import { Loader2Icon } from "lucide-react"

import type { StreamLine } from "@/hooks/use-gifty"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"

const kindColor: Record<StreamLine["kind"], string> = {
  info: "text-muted-foreground",
  node: "text-amber-600 dark:text-amber-400",
  result: "text-emerald-600 dark:text-emerald-400",
  error: "text-red-600 dark:text-red-400",
}

const kindMarker: Record<StreamLine["kind"], string> = {
  info: "text-muted-foreground/50",
  node: "text-amber-500",
  result: "text-emerald-500",
  error: "text-red-500",
}

interface StreamLogProps {
  lines: StreamLine[]
  active: boolean
}

export function StreamLog({ lines, active }: StreamLogProps) {
  const endRef = React.useRef<HTMLDivElement>(null)

  // Auto-scroll to the newest line; depends only on count to stay cheap.
  React.useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <div className="w-full animate-in overflow-hidden rounded-xl bg-muted/40 ring-1 ring-foreground/10 duration-300 fade-in slide-in-from-bottom-2">
      <div className="flex items-center gap-2 border-b bg-muted/60 px-4 py-2.5 text-sm font-medium">
        {active ? (
          <>
            <Loader2Icon className="size-4 animate-spin text-primary" />
            <span>Generating recommendations…</span>
          </>
        ) : (
          <>
            <span className="size-2 rounded-full bg-emerald-500" aria-hidden />
            <span>Run complete</span>
          </>
        )}
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {lines.length} steps
        </span>
      </div>
      <ScrollArea className="h-56">
        <ol className="flex flex-col gap-1.5 p-4 font-mono text-[0.8rem]">
          {lines.map((line) => (
            <li key={line.id} className="flex gap-2 leading-relaxed">
              <span
                className={cn("shrink-0 select-none", kindMarker[line.kind])}
              >
                ›
              </span>
              <span className="min-w-0">
                {line.contact && (
                  <span className="mr-1.5 rounded bg-foreground/10 px-1.5 py-0.5 text-[0.7rem] font-medium">
                    {line.contact}
                  </span>
                )}
                <span className={cn(kindColor[line.kind])}>{line.label}</span>
              </span>
            </li>
          ))}
          <div ref={endRef} />
        </ol>
      </ScrollArea>
    </div>
  )
}
