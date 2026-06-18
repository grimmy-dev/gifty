import * as React from "react"
import { AlertCircleIcon, CircleStopIcon, Trash2Icon, XIcon } from "lucide-react"

import { useGifty } from "@/hooks/use-gifty"
import { useRoute } from "@/hooks/use-route"
import { SAMPLE_JSON } from "@/lib/sample"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { AppHeader } from "@/components/gifty/app-header"
import { DetailPage } from "@/components/gifty/detail-page"
import { InputPanel } from "@/components/gifty/input-panel"
import { RecentPanel } from "@/components/gifty/recent-panel"
import { RecommendationCard } from "@/components/gifty/recommendation-card"
import { Roadmap } from "@/components/gifty/roadmap"

// Root: minimal path-based routing between the detail page and the main view.
export function App() {
  const path = useRoute()
  // /recommendation/:id renders the standalone detail page; everything else is main.
  const detail = path.match(/^\/recommendation\/([^/]+)$/)
  if (detail) return <DetailPage key={detail[1]} itemId={detail[1]} />

  return <MainView />
}

function MainView() {
  const [mode, setMode] = React.useState("post")
  const [input, setInput] = React.useState("")
  const gifty = useGifty()
  const {
    phase,
    runs,
    roadmap,
    runId,
    startedAt,
    isStreaming,
    error,
    review,
    rerun,
  } = gifty

  // Shrink the input panel once a run has started so results get the space.
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
          onRecommend={() => {
            gifty.recommend(input)
            setInput("")
          }}
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

        {(roadmap.length > 0 || runs.length > 0) && (
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
            <div className="flex items-center gap-2">
              {isStreaming && (
                <Button variant="outline" onClick={() => gifty.cancel()}>
                  <CircleStopIcon />
                  Stop
                </Button>
              )}
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
          </div>
        )}

        {roadmap.length > 0 && (
          <Roadmap
            phases={roadmap}
            active={isStreaming}
            startedAt={startedAt}
          />
        )}

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
