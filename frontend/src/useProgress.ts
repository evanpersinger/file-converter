import { useEffect, useState } from 'react'
import { getProgress } from './api'

const POLL_MS = 1000

/**
 * Live numbers for a running conversion: elapsed seconds, and the percent the backend
 * reports (null when it has none, which is every conversion except the local-model one).
 * Pass null when nothing is running and both reset.
 */
export function useProgress(jobId: string | null) {
  const [percent, setPercent] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!jobId) return

    const startedAt = Date.now()
    // A poll still in flight when the job ends must not write into the next one.
    let active = true

    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000))
      getProgress(jobId)
        .then((value) => {
          if (active) setPercent(value)
        })
        // A missed poll just leaves the last value on screen until the next one.
        .catch(() => {})
    }, POLL_MS)

    return () => {
      active = false
      clearInterval(timer)
      setElapsed(0)
      setPercent(null)
    }
  }, [jobId])

  return { percent, elapsed }
}
