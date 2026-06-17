import * as React from "react"
import { SendIcon, SparklesIcon, UploadIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const PLACEHOLDER = `
See sample data for knowing input format.
{
  "contacts": [
    {
      "name": "Jane Doe",
      "role": "Head of Product",
      "company": "Acme",
      "gift_context": { "occasion": "Thank you", "budget_min": 40, "budget_max": 80, "currency": "USD", "country": "USA" }
      ...
    }
  ]
}`

interface InputPanelProps {
  value: string
  onChange: (value: string) => void
  onRecommend: () => void
  onUseSample: () => void
  busy: boolean
  compact: boolean
}

export function InputPanel({
  value,
  onChange,
  onRecommend,
  onUseSample,
  busy,
  compact,
}: InputPanelProps) {
  const fileRef = React.useRef<HTMLInputElement>(null)

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onChange(await file.text())
    e.target.value = "" // allow re-uploading the same file
  }

  return (
    <div className="flex flex-col gap-3">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={PLACEHOLDER}
        spellCheck={false}
        disabled={busy}
        className={cn(
          "resize-none scrollbar-none rounded-xl p-4 font-mono text-xs leading-relaxed transition-[height] duration-300 ease-out",
          compact ? "h-28" : "h-72"
        )}
      />
      <div className="flex flex-wrap items-center gap-2.5">
        <Button
          size="lg"
          onClick={onRecommend}
          disabled={busy || !value.trim()}
        >
          <SendIcon />
          Recommend
        </Button>
        <Button
          size="lg"
          variant="secondary"
          onClick={onUseSample}
          disabled={busy}
        >
          <SparklesIcon />
          Use sample data
        </Button>
        <Button
          size="lg"
          variant="outline"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
        >
          <UploadIcon />
          Upload .json
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={onFile}
        />
      </div>
    </div>
  )
}
