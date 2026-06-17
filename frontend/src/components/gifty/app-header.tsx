import { GiftIcon } from "lucide-react"

import { TabsList, TabsTrigger } from "@/components/ui/tabs"

export function AppHeader() {
  return (
    <header className="flex animate-in flex-col items-center gap-6 text-center duration-500 fade-in slide-in-from-top-2">
      <div className="flex flex-col items-center gap-3">
        <span className="flex items-center justify-center gap-1.5 text-sm font-medium tracking-[0.2em] text-muted-foreground uppercase">
          <GiftIcon className="size-3.5 text-primary" />
          Gifty
        </span>
        <h1 className="font-heading text-4xl font-bold sm:text-5xl">
          Find the right gift for any contact
        </h1>
      </div>
      <p className="text-sm/relaxed text-balance text-muted-foreground">
        Add a contact and Gifty reads their profile, searches real in-budget
        products, and ranks three picks. Each one comes with a personalised note,
        ready for your review.
      </p>
      <TabsList aria-label="Switch view" className="space-x-2">
        <TabsTrigger value="post">
          Recommend
        </TabsTrigger>
        <TabsTrigger value="get">
          Recent
        </TabsTrigger>
      </TabsList>
    </header>
  )
}
