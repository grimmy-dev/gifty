import * as React from "react"

/** Copy text to clipboard with a transient "copied" flag. */
export function useCopy(resetMs = 1600) {
  const [copied, setCopied] = React.useState(false)
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  React.useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    []
  )

  const copy = React.useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        if (timer.current) clearTimeout(timer.current)
        timer.current = setTimeout(() => setCopied(false), resetMs)
      } catch {
        setCopied(false)
      }
    },
    [resetMs]
  )

  return { copied, copy }
}
