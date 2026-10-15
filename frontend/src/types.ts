/** A conversion the backend can actually perform right now. */
export interface Target {
  id: string
  label: string
  ext: string
  /** Which part of the UI owns it. Null means the regular "Convert to" list. */
  group: string | null
  note?: string
  /** A short sentence under its Markdown format button in the LLM tab. */
  caption?: string
  /** The LLM tab's Markdown format ("Typed PDF") and the provider running it ("local", "openai", "anthropic"). Null outside the LLM tab. */
  script: string | null
  provider: string | null
}

/** A conversion the backend knows about but cannot run, and why. */
export interface Unavailable {
  id: string
  label: string
  ext: string
  group: string | null
  caption?: string
  script: string | null
  provider: string | null
  reason: string
  hint?: string
}

/** An Ollama model the UI can offer. Not installed means it has to be pulled first. */
export interface LocalModel {
  name: string
  installed: boolean
}

/** The models one cloud provider offers. `reason` is set when its API key is missing. */
export interface CloudProvider {
  models: string[]
  reason?: string
  hint?: string
}

/**
 * One button in the model picker. `name` is the model's real name, which is what gets sent
 * and what shows on hover. `label` is what the button says when that reads better than
 * the name. `blocked` is why it can't be picked, shown on hover.
 */
export interface ModelOption {
  name: string
  label?: string
  blocked?: string
}

/** A headed list of model buttons. `message` is said alongside them when there is something to explain. */
export interface ModelGroupData {
  provider: string
  title: string
  message?: string
  models: ModelOption[]
}

/** The model the user picked, and the provider it belongs to. */
export interface PickedModel {
  provider: string
  name: string
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
