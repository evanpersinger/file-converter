// Parsing for .ipynb previews and the shared highlight.js loader FileViewer uses for
// both a plain .r file and a notebook's code cells.

import type { LanguageFn } from 'highlight.js'

export interface NotebookOutput {
  kind: 'text' | 'image' | 'error'
  text?: string
  imageUrl?: string
}

export interface NotebookCell {
  type: 'code' | 'markdown' | 'raw'
  source: string
  executionCount: number | null
  outputs: NotebookOutput[]
}

export interface ParsedNotebook {
  language: string
  cells: NotebookCell[]
}

// Each entry is a static import specifier so bundlers can code-split it, unlike a
// template-interpolated `import(`.../${language}`)`, which can't be analyzed the same way.
const LANGUAGE_LOADERS: Record<string, () => Promise<{ default: LanguageFn }>> = {
  python: () => import('highlight.js/lib/languages/python'),
  r: () => import('highlight.js/lib/languages/r'),
}

/**
 * Highlight `source` as `language`, or return null if that language isn't one of the
 * few registered above (rendered as plain text by the caller instead).
 */
export async function highlightCode(source: string, language: string): Promise<string | null> {
  const loadLanguage = LANGUAGE_LOADERS[language]
  if (!loadLanguage) return null

  // Loaded on demand so highlight.js and its grammars stay out of the initial bundle
  // for everyone who never previews a script or notebook.
  const [{ default: hljs }, { default: grammar }] = await Promise.all([
    import('highlight.js/lib/core'),
    loadLanguage(),
  ])
  // Registering is cheap, so it's fine to redo on every file opened rather than
  // tracking what's already registered.
  hljs.registerLanguage(language, grammar)
  return hljs.highlight(source, { language }).value
}

// eslint-disable-next-line no-control-regex -- deliberately matching the ANSI escape byte, to strip it
const ANSI_ESCAPE = /\u001b\[[0-9;]*m/g

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null
}

// nbformat allows a cell's source (and a stream output's text) as either one string
// or a list of lines to join, editors write it either way.
function joinSource(source: unknown): string {
  if (Array.isArray(source)) return source.join('')
  return typeof source === 'string' ? source : ''
}

function parseOutput(raw: unknown): NotebookOutput | null {
  const output = asRecord(raw)
  if (!output) return null

  if (output.output_type === 'error') {
    const traceback = Array.isArray(output.traceback) ? output.traceback.join('\n') : ''
    return { kind: 'error', text: traceback.replace(ANSI_ESCAPE, '') }
  }

  if (output.output_type === 'stream') {
    return { kind: 'text', text: joinSource(output.text) }
  }

  if (output.output_type === 'execute_result' || output.output_type === 'display_data') {
    const data = asRecord(output.data)
    if (!data) return null
    const png = data['image/png']
    if (typeof png === 'string') return { kind: 'image', imageUrl: `data:image/png;base64,${png}` }
    const text = data['text/plain']
    return text !== undefined ? { kind: 'text', text: joinSource(text) } : null
  }

  return null
}

/**
 * Parse nbformat JSON into cells FileViewer can render, or null if `raw` isn't a
 * recognizable notebook (the caller falls back to showing it as plain text).
 */
export function parseNotebook(raw: string): ParsedNotebook | null {
  let json: unknown
  try {
    json = JSON.parse(raw)
  } catch {
    return null
  }

  const root = asRecord(json)
  const rawCells = root?.cells
  if (!root || !Array.isArray(rawCells)) return null

  const metadata = asRecord(root.metadata)
  const kernelLanguage = asRecord(metadata?.kernelspec)?.language
  const languageInfoName = asRecord(metadata?.language_info)?.name
  const language =
    (typeof kernelLanguage === 'string' && kernelLanguage)
    || (typeof languageInfoName === 'string' && languageInfoName)
    || 'python'

  const cells: NotebookCell[] = rawCells.map((rawCell): NotebookCell => {
    const cell = asRecord(rawCell)
    const cellType = cell?.cell_type
    const outputs = Array.isArray(cell?.outputs)
      ? cell.outputs.map(parseOutput).filter((output): output is NotebookOutput => output !== null)
      : []

    return {
      type: cellType === 'code' || cellType === 'markdown' ? cellType : 'raw',
      source: joinSource(cell?.source),
      executionCount: typeof cell?.execution_count === 'number' ? cell.execution_count : null,
      outputs,
    }
  })

  return { language, cells }
}
