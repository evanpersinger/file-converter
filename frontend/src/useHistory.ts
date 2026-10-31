import { useCallback, useEffect, useState } from 'react'

/** One finished conversion. Only the name of the file that came out is kept, never the file itself. */
export interface HistoryEntry {
  id: string
  fileName: string
}

const STORAGE_KEY = 'file-converter-history'
export const MAX_HISTORY_ENTRIES = 20

function isEntry(value: unknown): value is HistoryEntry {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  return typeof entry.id === 'string' && typeof entry.fileName === 'string'
}

/** The saved entries, newest first. Empty when nothing is saved or the storage is blocked or unreadable. */
function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const saved: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(saved) ? saved.filter(isEntry).slice(0, MAX_HISTORY_ENTRIES) : []
  } catch {
    return []
  }
}

function saveHistory(entries: HistoryEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Storage is blocked or full (private window, say). The list still works until the page closes.
  }
}

/** The last conversions, newest first, kept in this browser's localStorage. */
export function useHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>(loadHistory)

  useEffect(() => saveHistory(entries), [entries])

  const record = useCallback((fileName: string) => {
    const entry: HistoryEntry = { id: crypto.randomUUID(), fileName }
    setEntries((current) => [entry, ...current].slice(0, MAX_HISTORY_ENTRIES))
  }, [])

  const clear = useCallback(() => setEntries([]), [])

  return { entries, record, clear }
}

export type HistoryState = ReturnType<typeof useHistory>
