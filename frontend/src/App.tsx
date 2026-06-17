import * as React from "react"
import { AlertCircleIcon, Trash2Icon, XIcon } from "lucide-react"

import { useGifty } from "@/hooks/use-gifty"
import { SAMPLE_JSON } from "@/lib/sample"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { AppHeader } from "@/components/gifty/app-header"
import { InputPanel } from "@/components/gifty/input-panel"
import { RecentPanel } from "@/components/gifty/recent-panel"
import { RecommendationCard } from "@/components/gifty/recommendation-card"
import { StreamLog } from "@/components/gifty/stream-log"

export function App() {
  const [mode, setMode] = React.useState("post")
  const [input, setInput] = React.useState("")
  const gifty = useGifty()
  const { phase, runs, log, runId, isStreaming, error, review, rerun } = gifty

  const compact = phase !== "idle"

  return (
    <Tabs
      value={mode}
      onValueChange={setMode}
      className="mx-auto flex min-h-svh w-full max-w-4xl flex-col gap-12 px-6 py-16 sm:py-20"
    >
      <AppHeader />

      <TabsContent value="post" className="flex flex-col gap-8">
        <InputPanel
          value={input}
          onChange={setInput}
          onRecommend={() => gifty.recommend(input)}
          onUseSample={() => setInput(SAMPLE_JSON)}
          busy={isStreaming}
          compact={compact}
        />

        {error && (
          <div
            role="alert"
            className="flex animate-in items-start gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive duration-300 fade-in slide-in-from-top-1"
          >
            <AlertCircleIcon className="mt-0.5 size-4 shrink-0" />
            <span className="flex-1">{error}</span>
            <button
              onClick={gifty.clearError}
              aria-label="Dismiss error"
              className="shrink-0 opacity-70 hover:opacity-100"
            >
              <XIcon className="size-4" />
            </button>
          </div>
        )}

        {(log.length > 0 || runs.length > 0) && (
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <h2 className="font-heading text-lg font-semibold">
                {isStreaming ? "Working" : "Results"}
              </h2>
              {runId && (
                <span className="font-mono text-xs text-muted-foreground">
                  run {runId}
                </span>
              )}
            </div>
            <Button
              variant="ghost"
              onClick={() => {
                gifty.clear()
                setInput("")
              }}
            >
              <Trash2Icon />
              Clear
            </Button>
          </div>
        )}

        {log.length > 0 && <StreamLog lines={log} active={isStreaming} />}

        {runs.length > 0 && (
          <section className="flex flex-col gap-6" aria-label="Recommendations">
            {runs.map((run) => (
              <RecommendationCard
                key={run.name}
                run={run}
                onReview={review}
                onRerun={rerun}
              />
            ))}
          </section>
        )}
      </TabsContent>

      <TabsContent value="get">
        <RecentPanel />
      </TabsContent>

      <footer className="mt-auto pt-4 text-center font-mono text-xs text-muted-foreground/70">
        Press <kbd className="rounded bg-muted px-1">d</kbd> to toggle theme
      </footer>
    </Tabs>
  )
}

export default App
