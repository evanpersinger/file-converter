import type { ApiError, CloudProvider, Detection, FormatMap, LocalModel } from './types'

export async function getFormats(): Promise<FormatMap> {
  const response = await fetch('/api/formats')
  if (!response.ok) {
    throw new Error('Could not reach the converter backend.')
  }
  return response.json()
}

/** Ollama models to offer. Empty when Ollama is not running. */
export async function getLocalModels(): Promise<LocalModel[]> {
  const response = await fetch('/api/local-models')
  if (!response.ok) {
    throw new Error('Could not load the local models.')
  }
  const payload: { models: LocalModel[] } = await response.json()
  return payload.models
}

/** The Whisper sizes to offer for video. */
export async function getSpeechModels(): Promise<string[]> {
  const response = await fetch('/api/speech-models')
  if (!response.ok) {
    throw new Error('Could not load the speech models.')
  }
  const payload: { models: string[] } = await response.json()
  return payload.models
}

/** The models each cloud provider offers, by provider name. */
export async function getCloudModels(): Promise<Record<string, CloudProvider>> {
  const response = await fetch('/api/cloud-models')
  if (!response.ok) {
    throw new Error('Could not load the cloud models.')
  }
  return response.json()
}

/**
 * Ask the backend whether the file's bytes match its extension. Advisory: a failure
 * here is swallowed by the caller rather than blocking the conversion.
 */
export async function detect(file: File): Promise<Detection> {
  const body = new FormData()
  body.append('file', file)

  const response = await fetch('/api/detect', { method: 'POST', body })
  if (!response.ok) {
    throw new Error('Could not inspect the file.')
  }
  return response.json()
}

export interface Converted {
  blob: Blob
  filename: string
  // Plain sentences about what happened to the file, empty when the route sends none.
  log: string[]
}

export async function convert(
  file: File,
  targetId: string,
  model: string | null = null,
  jobId: string | null = null,
  signal?: AbortSignal,
): Promise<Converted> {
  const body = new FormData()
  body.append('file', file)
  body.append('target', targetId)
  if (model) {
    body.append('model', model)
  }
  // Lets getProgress ask how far along this particular request is.
  if (jobId) {
    body.append('job_id', jobId)
  }

  const response = await fetch('/api/convert', { method: 'POST', body, signal })

  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Conversion failed'))
  }

  return {
    blob: await response.blob(),
    filename: filenameFrom(response.headers.get('Content-Disposition')),
    log: logFrom(response.headers.get('X-Conversion-Log')),
  }
}

/** Ask the backend to stop a running conversion after its current step. */
export async function cancelConversion(jobId: string): Promise<void> {
  const response = await fetch(`/api/convert/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' })
  if (!response.ok) {
    throw new Error('Could not cancel the conversion.')
  }
}

export interface Progress {
  // Percent done, or null when the backend has none to report.
  percent: number | null
  // True while the conversion waits behind another one that is still running.
  queued: boolean
}

/** How far along a running conversion is, and whether it has started yet. */
export async function getProgress(jobId: string): Promise<Progress> {
  const response = await fetch(`/api/progress/${encodeURIComponent(jobId)}`)
  if (!response.ok) {
    throw new Error('Could not read the conversion progress.')
  }
  return response.json()
}

/**
 * Combine several files of one format into one. Order matters: the files are merged
 * in the order given, which is the order the user added them.
 */
export async function combine(files: File[]): Promise<Converted> {
  const body = new FormData()
  for (const file of files) {
    body.append('files', file)
  }

  const response = await fetch('/api/combine', { method: 'POST', body })
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Combining failed'))
  }

  return {
    blob: await response.blob(),
    filename: filenameFrom(response.headers.get('Content-Disposition')),
    log: [],
  }
}

/** Unpack the backend's {error, hint} failure body into one message. */
async function errorMessage(response: Response, fallback: string): Promise<string> {
  let message = `${fallback} (${response.status}).`
  let hint: string | null | undefined
  try {
    const payload: ApiError = await response.json()
    message = payload.error ?? message
    hint = payload.hint
  } catch {
    // Non-JSON error body, keep the generic message.
  }
  return hint ? `${message}\n\n${hint}` : message
}

/**
 * Pull the download name out of the `Content-Disposition` header. The backend sends the
 * real name percent-encoded as `filename*=UTF-8''report.pdf`, which can hold any character,
 * next to a plain `filename="report.pdf"` fallback with the odd ones swapped for `_`. The
 * encoded one is read first.
 */
function filenameFrom(disposition: string | null): string {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)
  if (encoded) return decodeURIComponent(encoded[1])

  const plain = disposition?.match(/filename="(.+?)"/)
  return plain ? plain[1] : 'converted'
}

/** The sentences in the `X-Conversion-Log` header (a JSON list), or [] when it is missing or unreadable. */
function logFrom(header: string | null): string[] {
  if (!header) return []
  try {
    const lines: unknown = JSON.parse(header)
    return Array.isArray(lines) ? lines.filter((line): line is string => typeof line === 'string') : []
  } catch {
    return []
  }
}

/** Extension of a filename, lowercased and including the dot. "" if there is none. */
export function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot === -1 ? '' : filename.slice(dot).toLowerCase()
}
