/** A conversion the backend can actually perform right now. */
export interface Target {
  id: string
  label: string
  ext: string
  /** Which part of the UI owns it. Null means the regular "Convert to" list. */
  group: string | null
  note?: string
  /** A short sentence under its button, for telling apart LLM scripts that make the same format. */
  caption?: string
}

/** A conversion the backend knows about but cannot run, and why. */
export interface Unavailable {
  id: string
  label: string
  ext: string
  group: string | null
  caption?: string
  reason: string
  hint?: string
}

/** An Ollama model the UI can offer. Not installed means it has to be pulled first. */
export interface LocalModel {
  name: string
  installed: boolean
}

/** One output format, rendered as a single button in the grid. */
export interface FormatOption {
  ext: string
  name: string
}

/**
 * The whole format map, keyed by lowercased source extension (".csv", ".pdf").
 * The frontend hardcodes no extensions and no format names, it only indexes this
 * by the uploaded file's extension. Adding a converter is a backend-only change.
 */
export interface FormatMap {
  allFormats: FormatOption[]
  byExtension: Record<string, Target[]>
  unavailable: Record<string, Unavailable[]>
}

export interface ApiError {
  error: string
  hint?: string | null
}

/** A file whose contents contradict its extension. */
export interface Mismatch {
  named: string
  actual: string
}

export interface Detection {
  /** null when the two agree, or when the contents could not be identified. */
  mismatch: Mismatch | null
}
