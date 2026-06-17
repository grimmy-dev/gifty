import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Message from a caught error, falling back when it is not an Error. */
export function errMsg(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
}
