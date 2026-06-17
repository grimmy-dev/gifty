import { CheckIcon, CopyIcon } from "lucide-react"

import { useCopy } from "@/hooks/use-copy"
import { Button } from "@/components/ui/button"

interface CopyButtonProps {
  value: string
  label?: string
  size?: "sm" | "default" | "lg"
}

/** Copy-to-clipboard button with transient confirmation. */
export function CopyButton({
  value,
  label = "copy",
  size = "default",
}: CopyButtonProps) {
  const { copied, copy } = useCopy()
  return (
    <Button
      type="button"
      variant="outline"
      size={size}
      onClick={() => copy(value)}
      aria-label={copied ? "Copied to clipboard" : `Copy ${label}`}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
      {copied ? "copied" : label}
    </Button>
  )
}
