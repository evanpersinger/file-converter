import { useEffect, useRef, useState } from 'react'
import { combine, convert, detect, extensionOf, getFormats, getLocalModels } from './api'
import type { FormatMap, LocalModel, Mismatch, Target, Unavailable } from './types'
import ProgressBar from './ProgressBar'
import { useProgress } from './useProgress'
import './App.css'

type Status =
  | { kind: 'idle' }
  | { kind: 'converting'; fileName: string; position: number; total: number }
  | { kind: 'combining' }
  | { kind: 'error'; message: string }

interface Download {
  url: string
  filename: string
}

interface Result {
  downloads: Download[]
}

// Different spellings of one format. Kept in step with SUFFIX_ALIASES in
// combine_files.py, so the button enables exactly when the backend would accept.
const EXT_ALIASES: Record<string, string> = {
  '.jpeg': '.jpg',
  '.tif': '.tiff',
  '.htm': '.html',
}

const canonical = (ext: string) => EXT_ALIASES[ext] ?? ext

const blockedReason = (dep: Unavailable) =>
  dep.hint ? `${dep.reason}. ${dep.hint}` : dep.reason

const formatDuration = (seconds: number) =>
  seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`

export default function App() {
  const [formats, setFormats] = useState<FormatMap | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [target, setTarget] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [result, setResult] = useState<Result | null>(null)
  const [dragging, setDragging] = useState(false)
  const [mismatch, setMismatch] = useState<Mismatch | null>(null)
  // null while loading. An empty list is the answer when Ollama is off, and the reason
  // for that comes from the formats map.
  const [localModels, setLocalModels] = useState<LocalModel[] | null>(null)
  // The model picked from the LLM script's list.
  const [model, setModel] = useState<string | null>(null)
  // Set while a conversion is running, so the backend can be asked how far along it is.
  const [jobId, setJobId] = useState<string | null>(null)
  const { percent, elapsed } = useProgress(jobId)
  // Which file the newest detect() call was for. Adding a second file while the
  // first check is in flight would otherwise let the stale answer win.
  const latestPick = useRef<File | null>(null)

  useEffect(() => {
    getFormats().then(setFormats).catch((e: Error) => setLoadError(e.message))
    getLocalModels().then(setLocalModels).catch(() => setLocalModels([]))
  }, [])

  // Release the blob URL when it gets replaced or the page unmounts. Without this,
  // every conversion would leak its result until a full page reload.
  useEffect(() => {
    if (!result) return
    return () => result.downloads.forEach((d) => URL.revokeObjectURL(d.url))
  }, [result])

  // A file dropped anywhere but the picker makes the browser navigate to it, which
  // throws away whatever is on screen. Swallow drops outside the target.
  useEffect(() => {
    const swallow = (e: DragEvent) => e.preventDefault()
    window.addEventListener('dragover', swallow)
    window.addEventListener('drop', swallow)
    return () => {
      window.removeEventListener('dragover', swallow)
      window.removeEventListener('drop', swallow)
    }
  }, [])

  // The first file drives the format buttons and the mismatch check. Combining
  // requires everything to share one extension anyway, so it is representative.
  const primary = files[0] ?? null
  const ext = primary ? extensionOf(primary.name) : ''
  const forFile = (ext && formats?.byExtension[ext]) || []
  const blockedForFile = (ext && formats?.unavailable[ext]) || []
  // LLM scripts have their own column, so "Convert to" only sees the ungrouped ones.
  const targets = forFile.filter((t) => !t.group)
  const blocked = blockedForFile.filter((u) => !u.group)
  const llmTargets = forFile.filter((t) => t.group === 'llm')
  const llmBlocked = blockedForFile.filter((u) => u.group === 'llm')

  const distinctExts = [...new Set(files.map((f) => canonical(extensionOf(f.name))))]
  const mixedExtensions = files.length >= 2 && distinctExts.length > 1
  const canCombine = files.length >= 2 && !mixedExtensions
  const busy = status.kind === 'converting' || status.kind === 'combining'

  // Which conversion owns a format button. Registry order decides: pdf->md is
  // registered before pdf->md-ai, and img->txt before img->txt-tables, so the first
  // match is always the free local route and anything after it is an opt-in variant.
  const routesFor = (formatExt: string) => targets.filter((t) => t.ext === formatExt)

  const selected = targets.find((t) => t.id === target) ?? null
  const selectedLlm = llmTargets.find((t) => t.id === target) ?? null
  const variants = selected ? routesFor(selected.ext).slice(1) : []

  // One button per output format an LLM script makes. Read off the map rather than
  // hardcoded, so it shows before a file is chosen and a new script adds its own.
  const llmFormats = formats
    ? formats.allFormats.filter((f) =>
        [...Object.values(formats.byExtension), ...Object.values(formats.unavailable)]
          .flat()
          .some((t) => t.group === 'llm' && t.ext === f.ext),
      )
    : []

  // The target borrows the registry's display name so both boxes read the same way.
  const sourceName = ext ? ext.slice(1).toUpperCase() : null
  const shownTarget = selected ?? selectedLlm
  const targetName = formats?.allFormats.find((f) => f.ext === shownTarget?.ext)?.name ?? null

  function runDetect(file: File) {
    latestPick.current = file
    // Advisory only. If the check itself fails there is nothing useful to say, so
    // it stays silent rather than showing an error for a file that may convert fine.
    detect(file)
      .then((d) => {
        if (latestPick.current === file) setMismatch(d.mismatch)
      })
      .catch(() => {})
  }

  function addFiles(incoming: FileList | null) {
    const added = Array.from(incoming ?? [])
    if (added.length === 0) return

    setStatus({ kind: 'idle' })
    setResult(null)

    // Appending rather than replacing is what makes the order first-come-first-served
    // across several picks. The backend merges in exactly this order.
    if (files.length === 0) {
      setTarget(null)
      setMismatch(null)
      runDetect(added[0])
    }
    setFiles([...files, ...added])
  }

  function clearFiles() {
    setFiles([])
    setStatus({ kind: 'idle' })
    setResult(null)
    setTarget(null)
    setMismatch(null)
    latestPick.current = null
  }

  function removeAt(index: number) {
    const next = files.filter((_, i) => i !== index)
    if (next.length === 0) {
      clearFiles()
      return
    }

    setFiles(next)
    setStatus({ kind: 'idle' })
    setResult(null)

    if (index === 0) {
      // The first file drives everything, so dropping it invalidates the target and
      // the mismatch answer.
      setTarget(null)
      setMismatch(null)
      runDetect(next[0])
    }
  }

  // Clicking an LLM script selects it, which puts its format in the To box, clears any
  // "Convert to" selection, and opens its model list. Clicking it again deselects it.
  // Either way the model starts over, so a script is never run with an old pick.
  function toggleLlm(route: Target) {
    setTarget(selectedLlm?.id === route.id ? null : route.id)
    setModel(null)
  }

  async function run(action: (jobId: string) => Promise<{ blob: Blob; filename: string }>,
                     running: Status) {
    const id = crypto.randomUUID()
    setStatus(running)
    setResult(null)
    setJobId(id)
    try {
      const { blob, filename } = await action(id)
      // Hold the result and let the user click Download, rather than firing the
      // download automatically.
      setResult({ downloads: [{ url: URL.createObjectURL(blob), filename }] })
      setStatus({ kind: 'idle' })
    } catch (e) {
      setStatus({ kind: 'error', message: (e as Error).message })
    } finally {
      setJobId(null)
    }
  }

  // Converts the files one after another, since the server runs one conversion at a
  // time anyway. A failed file doesn't stop the rest, and the ones that worked stay
  // downloadable next to the error naming the ones that didn't.
  async function convertAll(targetId: string) {
    const downloads: Download[] = []
    const failures: string[] = []
    setResult(null)

    for (const [index, file] of files.entries()) {
      const id = crypto.randomUUID()
      setStatus({ kind: 'converting', fileName: file.name, position: index + 1, total: files.length })
      setJobId(id)
      try {
        const { blob, filename } = await convert(file, targetId, selectedLlm ? model : null, id)
        downloads.push({ url: URL.createObjectURL(blob), filename })
      } catch (e) {
        failures.push(`${file.name}: ${(e as Error).message}`)
      }
    }

    setJobId(null)
    if (downloads.length > 0) {
      setResult({ downloads })
    }
    setStatus(failures.length > 0 ? { kind: 'error', message: failures.join('\n\n') } : { kind: 'idle' })
  }

  const pickerLabel =
    files.length === 0 ? 'Choose or drop a file'
      : files.length === 1 ? files[0].name
        : `${files.length} files`

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>Convert to</h2>

        <div className="formats">
          {formats?.allFormats.map((f) => {
            const route = routesFor(f.ext)[0]
            const dep = blocked.find((u) => u.ext === f.ext)
            // Every disabled button says why on hover, so a greyed-out list is never
            // just a dead end.
            const why = route
              ? undefined
              : files.length === 0
                ? 'Add a file to see what file type it can be converted to'
                : dep
                  ? blockedReason(dep)
                  : `Cannot convert ${ext || 'this file'} to ${f.name}.`

            return (
              <span key={f.ext} className="tip" data-tip={why}>
                <button
                  type="button"
                  className={selected?.ext === f.ext ? 'format selected' : 'format'}
                  disabled={!route}
                  onClick={() => route && setTarget(selected?.ext === f.ext ? null : route.id)}
                >
                  {f.name}
                </button>
              </span>
            )
          })}
        </div>

        {files.length > 0 && targets.length === 0 && (
          <p className="muted">Nothing can convert {ext || 'this file'} yet.</p>
        )}

        {variants.map((v) => (
          <label key={v.id} className="option">
            <input
              type="checkbox"
              checked={target === v.id}
              onChange={(e) => setTarget(e.target.checked ? v.id : routesFor(v.ext)[0].id)}
            />
            <span>{v.label}</span>
          </label>
        ))}
      </aside>

      <aside className="sidebar llm-panel">
        <h2>Convert to</h2>
        <p className="muted subtitle">Scripts use LLMs for conversion.</p>

        <div className="formats">
          {llmFormats.map((f) => {
            const route = llmTargets.find((t) => t.ext === f.ext)
            const dep = llmBlocked.find((u) => u.ext === f.ext)
            const why = route
              ? undefined
              : files.length === 0
                ? 'Add a file to see which LLM scripts can convert it'
                : dep
                  ? blockedReason(dep)
                  : `No LLM script can convert ${ext || 'this file'} to ${f.name}.`

            return (
              <span key={f.ext} className="tip" data-tip={why}>
                <button
                  type="button"
                  className={selectedLlm?.ext === f.ext ? 'format selected' : 'format'}
                  disabled={!route}
                  onClick={() => route && toggleLlm(route)}
                >
                  {f.name}
                </button>
              </span>
            )
          })}
        </div>

        {selectedLlm && (
          <div className="model-list">
            <p className="muted">OS models</p>

            {localModels === null && <p className="muted">Loading models...</p>}

            {localModels?.length === 0 && (
              <p className="muted">No models found. Is Ollama running?</p>
            )}

            {localModels && localModels.length > 0 && !localModels.some((m) => m.installed) && (
              <p className="muted">Nothing downloaded yet. Hover a model to see how to get it.</p>
            )}

            {localModels?.map((m) => (
              <span
                key={m.name}
                className="tip"
                data-tip={m.installed ? undefined : `Not downloaded. Run: ollama pull ${m.name}`}
              >
                <button
                  type="button"
                  className={model === m.name ? 'format selected' : 'format'}
                  disabled={!m.installed}
                  title={m.name}
                  onClick={() => setModel(model === m.name ? null : m.name)}
                >
                  {m.name}
                </button>
              </span>
            ))}

            {selectedLlm.note && <p className="muted note">{selectedLlm.note}</p>}
          </div>
        )}
      </aside>

      <main>
        {loadError && <p className="error">{loadError}</p>}

        <div className="picker-row">
          <label
            className={dragging ? 'filepicker dragging' : 'filepicker'}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            // dragleave also fires when the cursor crosses onto a child, so without the
            // contains() check the highlight flickers as you move over the label text.
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false)
            }}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              addFiles(e.dataTransfer.files)
            }}
          >
            <input
              type="file"
              multiple
              onChange={(e) => {
                addFiles(e.target.files)
                // Clearing the value lets the same file be picked again after removing
                // it, which otherwise fires no change event.
                e.target.value = ''
              }}
            />
            <span title={files.length === 1 ? files[0].name : undefined}>{pickerLabel}</span>
          </label>

          {/* Disabled while converting: the loop keeps going over the files it started
              with, so clearing mid-batch would bring download links back for them. */}
          <button
            type="button"
            className="clear"
            onDoubleClick={clearFiles}
            disabled={files.length === 0 || busy}
          >
            Clear
            <span className="clear-hint">Click twice to clear</span>
          </button>
        </div>

        {files.length > 0 && (
          <ol className={files.length > 1 ? 'filelist numbered' : 'filelist'}>
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`}>
                <span title={f.name}>{f.name}</span>
                <button
                  type="button"
                  className="remove"
                  onClick={() => removeAt(i)}
                  aria-label={`Remove ${f.name}`}
                >
                  &times;
                </button>
              </li>
            ))}
          </ol>
        )}

        {mismatch && (
          <p className="warning">
            This file is named <code>{mismatch.named}</code> but its contents are
            actually <code>{mismatch.actual}</code>. The conversions offered are the
            ones for <code>{mismatch.named}</code>, so they will likely fail or give
            you garbage. Renaming it to <code>{mismatch.actual}</code> will fix it.
          </p>
        )}

        {mixedExtensions && (
          <p className="warning">
            Converting and combining both need every file to be the same format,
            and these are {distinctExts.join(', ')}. Remove the odd ones out.
          </p>
        )}

        <div className="transfer">
          <div className="slot">
            <div className={sourceName ? 'box filled' : 'box'}>
              <span className="box-value">{sourceName ?? '--'}</span>
            </div>
            <span className="box-label">From</span>
          </div>
          <div className="slot">
            <div className={targetName ? 'box filled' : 'box'}>
              <span className="box-value">{targetName ?? '--'}</span>
            </div>
            <span className="box-label">To</span>
          </div>
        </div>

        <div className="actions">
          <span
            className="tip"
            data-tip={
              files.length === 0
                ? 'Add files to convert'
                : mixedExtensions
                  ? 'Every file has to be the same format'
                  : !target
                    ? 'Pick a format, or an LLM script, to convert with'
                    : selectedLlm && !model
                      ? 'Pick a model to convert with'
                      : undefined
            }
          >
            <button
              className="action"
              onClick={() => target && convertAll(target)}
              disabled={
                files.length === 0 || mixedExtensions || !target
                || (selectedLlm !== null && !model) || busy
              }
            >
              {status.kind === 'converting' ? 'Converting...' : 'Convert Files'}
            </button>
          </span>

          <span
            className="tip"
            data-tip={
              files.length === 0
                ? 'Add files to combine'
                : files.length < 2
                  ? 'Add two or more files to combine'
                  : mixedExtensions
                    ? 'Every file has to be the same format'
                    : undefined
            }
          >
            <button
              className="action"
              onClick={() => run(() => combine(files), { kind: 'combining' })}
              disabled={!canCombine || busy}
            >
              {status.kind === 'combining' ? 'Combining...' : 'Combine Files'}
            </button>
          </span>
        </div>

        <button
          type="button"
          className="clear-converted"
          onDoubleClick={() => setResult(null)}
          disabled={!result}
        >
          Clear
          <span className="clear-hint">Click twice to clear</span>
        </button>

        {status.kind === 'converting' && (
          <div className="progress-block">
            <p className="progress-title" title={status.fileName}>
              Converting {status.total > 1 && `${status.position} of ${status.total}: `}
              {status.fileName}.
            </p>
            <ProgressBar percent={percent} />
            <p className="muted progress-time">{formatDuration(elapsed)}</p>
          </div>
        )}

        {result?.downloads.map((d) => (
          <a key={d.url} className="download" href={d.url} download={d.filename}>
            Download {d.filename}
          </a>
        ))}

        {status.kind === 'error' && <pre className="error">{status.message}</pre>}
      </main>
    </div>
  )
}
