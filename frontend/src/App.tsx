import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  cancelConversion, combine, convert, detect, extensionOf, getCloudModels, getFormats, getLocalModels,
  getSpeechModels,
} from './api'
import type {
  CloudProvider, FormatMap, LocalModel, Mismatch, ModelGroupData, PickedModel,
} from './types'
import FileViewer from './FileViewer'
import { combineLimitMessage, convertLimitMessage, overDetectLimit } from './limits'
import ModelGroup from './ModelGroup'
import ProgressBar from './ProgressBar'
import { useHistory, type HistoryState } from './useHistory'
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
  // Kept alongside the object URL so View can build a File out of it on demand.
  blob: Blob
}

interface Result {
  downloads: Download[]
}

// What the far-right panel says about one file of a conversion.
interface LogEntry {
  id: string
  fileName: string
  // The name of the format it became (Markdown, PDF), null when the conversion failed.
  convertedTo: string | null
  lines: string[]
  // A whole-file failure, drawn like the red error block instead of a plain note.
  failed: boolean
}

// One click of Convert. Every file from it sits in the same section of the Result panel.
interface ConversionRun {
  id: string
  files: LogEntry[]
}

// How many runs the Result panel keeps, newest first.
const MAX_LOG_RUNS = 10

// Different spellings of one format. Kept in step with SUFFIX_ALIASES in
// combine_files.py, so the button enables exactly when the backend would accept.
const EXT_ALIASES: Record<string, string> = {
  '.jpeg': '.jpg',
  '.tif': '.tiff',
  '.htm': '.html',
}

const canonical = (ext: string) => EXT_ALIASES[ext] ?? ext

// Gap between the downloads Download All starts. Browsers can drop downloads that fire
// back to back, so each one waits its turn.
const DOWNLOAD_GAP_MS = 300

const blockedReason = (dep: { reason: string; hint?: string }) =>
  dep.hint ? `${dep.reason}. ${dep.hint}` : dep.reason

const formatDuration = (seconds: number) =>
  seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`

// Adds freshly converted files to the ones already listed. An earlier result is only
// replaced by one with the same name and extension, so converting a file to a second
// format leaves the first result alone. Files in `added` never replace each other.
function mergeDownloads(existing: Download[], added: Download[]): Download[] {
  const replaced = new Set(added.map((d) => d.filename))
  return [...existing.filter((d) => !replaced.has(d.filename)), ...added]
}

// The Markdown formats in the LLM tab, one per script, in registry order. A format has a
// route for each provider, and the model picked decides which one runs, so it is listed
// once however many routes it has. Read off the map rather than hardcoded, so the buttons
// show before a file is chosen and a new script adds its own. The caption comes from
// whichever of its routes has one.
function llmScriptsIn(formats: FormatMap | null): { script: string; caption?: string }[] {
  const routes = formats
    ? [...Object.values(formats.byExtension), ...Object.values(formats.unavailable)].flat()
    : []
  const captions = new Map<string, string | undefined>()
  for (const route of routes) {
    if (route.group === 'llm' && route.script) {
      captions.set(route.script, captions.get(route.script) ?? route.caption)
    }
  }
  return [...captions].map(([script, caption]) => ({ script, caption }))
}

function localGroup(models: LocalModel[] | null): ModelGroupData {
  const message =
    models === null ? 'Loading models...'
      : models.length === 0 ? 'No models found. Is Ollama running?'
        : models.some((m) => m.installed) ? undefined
          : 'Nothing downloaded yet. Hover a model to see how to get it'

  return {
    provider: 'local',
    title: 'Open Source models',
    message,
    models: (models ?? []).map((m) => ({
      name: m.name,
      blocked: m.installed ? undefined : `Not downloaded. Run: ollama pull ${m.name}`,
    })),
  }
}

// What a cloud model's button says when the provider's name for it reads badly. The real
// name is still what gets sent, and it shows on hover.
const MODEL_LABELS: Record<string, string> = {
  'claude-haiku-4-5-20251001': 'haiku 4-5',
  'claude-sonnet-5': 'sonnet 5',
}

function cloudGroup(
  provider: string,
  title: string,
  providers: Record<string, CloudProvider> | null,
): ModelGroupData {
  const entry = providers?.[provider]
  const blocked = entry?.reason ? blockedReason({ reason: entry.reason, hint: entry.hint }) : undefined

  return {
    provider,
    title,
    message: providers === null ? 'Loading models...' : entry ? undefined : 'Could not load models',
    models: (entry?.models ?? []).map((name) => ({ name, label: MODEL_LABELS[name], blocked })),
  }
}

// The Whisper sizes, which run on this machine like the Ollama models do. They download the
// first time one is used, so unlike those there is nothing to say about whether one is there.
function speechGroup(models: string[] | null): ModelGroupData {
  return {
    provider: 'whisper',
    title: 'Speech models',
    message:
      models === null ? 'Loading models...'
        : models.length === 0 ? 'Could not load models'
          : undefined,
    models: (models ?? []).map((name) => ({ name })),
  }
}

// Greys out every model in a group, saying why on hover. The reason replaces any a model
// already had, since fixing that one would not make the group able to run this file.
function blockGroup(group: ModelGroupData, reason: string): ModelGroupData {
  return { ...group, models: group.models.map((m) => ({ ...m, blocked: reason })) }
}

type Tab = 'convert' | 'llm'

const TABS: { id: Tab; label: string }[] = [
  { id: 'convert', label: 'Convert Files' },
  { id: 'llm', label: 'Convert Files (LLM)' },
]

// The tab bar and a converter for each tab. Both stay mounted and the inactive one is hidden,
// so each tab keeps its own files, results and picks, and a conversion keeps running while
// the other tab is showing.
export default function App() {
  const [tab, setTab] = useState<Tab>('convert')
  // One list for both tabs, so each tab's Result panel shows the same recent conversions.
  const history = useHistory()

  return (
    <div className="app">
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? 'format selected' : 'format'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {TABS.map((t) => (
        <Converter key={t.id} tab={t.id} active={tab === t.id} history={history} />
      ))}
    </div>
  )
}

function Converter({ tab, active, history }: { tab: Tab; active: boolean; history: HistoryState }) {
  const [formats, setFormats] = useState<FormatMap | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [target, setTarget] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [result, setResult] = useState<Result | null>(null)
  const [dragging, setDragging] = useState(false)
  const [mismatch, setMismatch] = useState<Mismatch | null>(null)
  // The dropped file currently shown in the preview overlay, null when it's closed.
  const [viewing, setViewing] = useState<File | null>(null)
  // null while loading. An empty list is the answer when Ollama is off, and the reason
  // for that comes from the formats map.
  const [localModels, setLocalModels] = useState<LocalModel[] | null>(null)
  // Same idea for the cloud providers' models, by provider name.
  const [cloudModels, setCloudModels] = useState<Record<string, CloudProvider> | null>(null)
  // The Whisper sizes for video, null while loading.
  const [speechModels, setSpeechModels] = useState<string[] | null>(null)
  // The two picks in the LLM tab. They are independent, and together decide the route: the
  // Markdown format names the script, the model's provider names which of its routes runs.
  const [script, setScript] = useState<string | null>(null)
  const [model, setModel] = useState<PickedModel | null>(null)
  // Set while a conversion is running, so the backend can be asked how far along it is.
  const [jobId, setJobId] = useState<string | null>(null)
  // True once Cancel has been clicked for the current job, so the button can't be
  // clicked twice while the backend is still winding the job down.
  const [cancelling, setCancelling] = useState(false)
  // The sentences about each conversion run, newest first: one section per run, one entry
  // per file. They stay until the page is reloaded.
  const [conversionRuns, setConversionRuns] = useState<ConversionRun[]>([])
  const { percent, queued, elapsed } = useProgress(jobId)
  // Which file the newest detect() call was for. Adding a second file while the
  // first check is in flight would otherwise let the stale answer win.
  const latestPick = useRef<File | null>(null)
  // Set by Cancel, checked before each file in convertAll's loop so a multi-file batch
  // stops picking up new files.
  const cancelledBatch = useRef(false)
  // The AbortController for whichever file convertAll is currently awaiting, so Cancel
  // can drop the connection instead of waiting for a file with no way to stop mid-file.
  const currentAbort = useRef<AbortController | null>(null)
  // Whether the running batch is the local-model route, set once per batch. That route
  // stops itself after the current page and returns a partial file, so Cancel must not
  // abort its request too, that would throw the partial result away.
  const localModelRun = useRef(false)

  useEffect(() => {
    getFormats().then(setFormats).catch((e: Error) => setLoadError(e.message))
    getLocalModels().then(setLocalModels).catch(() => setLocalModels([]))
    getCloudModels().then(setCloudModels).catch(() => setCloudModels({}))
    getSpeechModels().then(setSpeechModels).catch(() => setSpeechModels([]))
  }, [])

  // Release a blob URL once it is no longer in `result`, whether a new conversion
  // replaced it or it was removed from the list. Without this, every conversion would
  // leak its files until a full page reload. It is tracked in a ref rather than revoked
  // in a cleanup, since a cleanup would also release the files that are staying.
  const shownUrls = useRef<string[]>([])

  useEffect(() => {
    const current = result?.downloads.map((d) => d.url) ?? []
    shownUrls.current
      .filter((url) => !current.includes(url))
      .forEach((url) => URL.revokeObjectURL(url))
    shownUrls.current = current
  }, [result])

  useEffect(() => () => shownUrls.current.forEach((url) => URL.revokeObjectURL(url)), [])

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
  // LLM routes have their own tab, so "Convert to" only sees the ungrouped ones.
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
  const variants = selected ? routesFor(selected.ext).slice(1) : []

  // The LLM tab's route, once both a Markdown format and a model are picked.
  const llmRoute = llmTargets.find((t) => t.script === script && t.provider === model?.provider) ?? null
  const llmScripts = llmScriptsIn(formats)
  // With a file loaded, a group with no route for its type is greyed out, since picking one
  // of its models could never run. A route that is only blocked (no API key, Ollama off)
  // still counts, that group has its own reason to show.
  const providersForFile = new Set([...llmTargets, ...llmBlocked].map((t) => t.provider))
  const modelGroups = [
    localGroup(localModels),
    cloudGroup('openai', 'OpenAI models', cloudModels),
    cloudGroup('anthropic', 'Anthropic models', cloudModels),
    speechGroup(speechModels),
  ].map((g) =>
    formats && files.length > 0 && !providersForFile.has(g.provider)
      ? blockGroup(g, `These models cannot convert ${ext || 'this file'}`)
      : g,
  )

  // What Convert runs, and what is still missing when it can't.
  const runTarget = tab === 'llm' ? (llmRoute?.id ?? null) : target
  const missingPick =
    tab !== 'llm' ? 'Pick a format to convert with'
      : script && model ? 'That model cannot run this format on this file'
        : script ? 'Pick a model to convert with'
          : model ? 'Pick a Markdown format to convert with'
            : 'Pick a Markdown format and a model to convert with'

  // The target borrows the registry's display name so both boxes read the same way.
  const sourceName = ext ? ext.slice(1).toUpperCase() : null
  const shownTarget = selected ?? llmRoute ?? llmTargets.find((t) => t.script === script) ?? null
  const targetName = formats?.allFormats.find((f) => f.ext === shownTarget?.ext)?.name ?? null

  function runDetect(file: File) {
    latestPick.current = file
    // The server refuses to inspect a file over the convert limit, and only after taking the
    // whole upload, so don't send one just to be turned away.
    if (overDetectLimit(file)) return
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

    // Appending rather than replacing is what makes the order first-come-first-served
    // across several picks. The backend merges in exactly this order.
    if (files.length === 0) {
      clearFormatPicks()
      pickOnlyScript(added[0])
      setMismatch(null)
      runDetect(added[0])
    }
    setFiles([...files, ...added])
  }

  function clearFiles() {
    setFiles([])
    setStatus({ kind: 'idle' })
    clearFormatPicks()
    setMismatch(null)
    latestPick.current = null
  }

  function removeDownload(url: string) {
    setResult((current) => {
      const downloads = current?.downloads.filter((d) => d.url !== url) ?? []
      return downloads.length > 0 ? { downloads } : null
    })
  }

  function downloadAll() {
    result?.downloads.forEach((d, index) => {
      setTimeout(() => {
        const link = document.createElement('a')
        link.href = d.url
        link.download = d.filename
        link.click()
      }, index * DOWNLOAD_GAP_MS)
    })
  }

  function removeAt(index: number) {
    const next = files.filter((_, i) => i !== index)
    if (next.length === 0) {
      clearFiles()
      return
    }

    setFiles(next)
    setStatus({ kind: 'idle' })

    if (index === 0) {
      // The first file drives everything, so dropping it invalidates the target and
      // the mismatch answer.
      clearFormatPicks()
      pickOnlyScript(next[0])
      setMismatch(null)
      runDetect(next[0])
    }
  }

  // The format picks belong to the first file, so they go when it does. The model stays,
  // it doesn't depend on the file.
  function clearFormatPicks() {
    setTarget(null)
    setScript(null)
  }

  // A Markdown format that is the only one the file can use is picked for the user, there is
  // nothing to choose between. Only the LLM tab has these formats.
  function pickOnlyScript(file: File) {
    if (tab !== 'llm') return
    const scripts = new Set(
      (formats?.byExtension[extensionOf(file.name)] ?? [])
        .filter((t) => t.group === 'llm')
        .map((t) => t.script),
    )
    if (scripts.size === 1) setScript([...scripts][0])
  }

  // Clicking a picked model again deselects it.
  function pickModel(provider: string, name: string) {
    const same = model?.provider === provider && model.name === name
    setModel(same ? null : { provider, name })
  }

  async function run(action: (jobId: string) => Promise<{ blob: Blob; filename: string }>,
                     running: Status) {
    const id = crypto.randomUUID()
    setStatus(running)
    setJobId(id)
    try {
      const { blob, filename } = await action(id)
      const download = { url: URL.createObjectURL(blob), filename, blob }
      history.record(filename)
      // Hold the result and let the user click Download, rather than firing the
      // download automatically.
      setResult((current) => ({ downloads: mergeDownloads(current?.downloads ?? [], [download]) }))
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
    const limitMessage = convertLimitMessage(files)
    if (limitMessage) {
      setStatus({ kind: 'error', message: limitMessage })
      return
    }

    const downloads: Download[] = []
    const failures: string[] = []
    cancelledBatch.current = false
    localModelRun.current = llmRoute?.provider === 'local'
    const modelName = llmRoute ? (model?.name ?? null) : null
    const runId = crypto.randomUUID()

    // The first file of the run starts its section, so no empty section shows while the
    // first file is still converting. The rest join it.
    const addLog = (fileName: string, convertedTo: string | null, lines: string[]) => {
      const entry: LogEntry = {
        id: crypto.randomUUID(),
        fileName,
        convertedTo,
        lines,
        failed: convertedTo === null,
      }
      setConversionRuns((current) => {
        const [latest, ...older] = current
        return latest?.id === runId
          ? [{ ...latest, files: [...latest.files, entry] }, ...older]
          : [{ id: runId, files: [entry] }, ...current].slice(0, MAX_LOG_RUNS)
      })
    }

    for (const [index, file] of files.entries()) {
      if (cancelledBatch.current) {
        addLog(file.name, null, ['Not converted: the batch was cancelled.'])
        continue
      }
      const id = crypto.randomUUID()
      const controller = new AbortController()
      currentAbort.current = controller
      setStatus({ kind: 'converting', fileName: file.name, position: index + 1, total: files.length })
      setJobId(id)
      setCancelling(false)
      try {
        const { blob, filename, log } = await convert(file, targetId, modelName, id, controller.signal)
        downloads.push({ url: URL.createObjectURL(blob), filename, blob })
        history.record(filename)
        const outExt = extensionOf(filename)
        const formatName = formats?.allFormats.find((f) => f.ext === outExt)?.name ?? outExt.slice(1).toUpperCase()
        addLog(file.name, formatName || filename, log)
      } catch (e) {
        // A cancelled file is listed in the Result panel, but isn't a failure to report.
        if (e instanceof DOMException && e.name === 'AbortError') {
          addLog(file.name, null, ['Conversion cancelled.'])
        } else {
          failures.push(`${file.name}: ${(e as Error).message}`)
          addLog(file.name, null, [(e as Error).message])
        }
      }
    }

    setJobId(null)
    if (downloads.length > 0) {
      setResult((current) => ({ downloads: mergeDownloads(current?.downloads ?? [], downloads) }))
    }
    setStatus(failures.length > 0 ? { kind: 'error', message: failures.join('\n\n') } : { kind: 'idle' })
  }

  function combineAll() {
    const limitMessage = combineLimitMessage(files)
    if (limitMessage) {
      setStatus({ kind: 'error', message: limitMessage })
      return
    }
    run(() => combine(files), { kind: 'combining' })
  }

  // Stops the batch from picking up the next file. For the local-model route the
  // current file's request is left running, it resolves once the backend stops after
  // its current page and hands back the partial file. Everything else has no way to
  // stop mid-file server-side, so the request is aborted instead of waited on.
  async function cancelCurrentJob() {
    cancelledBatch.current = true
    if (!localModelRun.current) {
      currentAbort.current?.abort()
    }
    if (!jobId) return
    setCancelling(true)
    try {
      await cancelConversion(jobId)
    } catch {
      setCancelling(false)
    }
  }

  const pickerLabel =
    files.length === 0 ? 'Choose or drop a file'
      : files.length === 1 ? files[0].name
        : `${files.length} files`

  return (
    <div className="layout" data-tab={tab} hidden={!active}>
      <aside className="sidebar" hidden={tab !== 'convert'}>
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
                  : `Cannot convert ${ext || 'this file'} to ${f.name}`

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
          <p className="muted">
            {llmTargets.length > 0 || llmBlocked.length > 0
              ? `${ext} can only be converted in the LLM tab`
              : `Nothing can convert ${ext || 'this file'} yet`}
          </p>
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

      <aside className="sidebar model-panel" hidden={tab !== 'llm'}>
        <h2>Model</h2>

        <div className="model-groups">
          {modelGroups.map((g) => (
            <ModelGroup
              key={g.provider}
              group={g}
              picked={model?.provider === g.provider ? model.name : null}
              onPick={(name) => pickModel(g.provider, name)}
            />
          ))}
        </div>

        {llmRoute?.note && <p className="muted note">{llmRoute.note}</p>}
      </aside>

      <aside className="sidebar" hidden={tab !== 'llm'}>
        <h2>Markdown (MD)</h2>

        <div className="llm-routes">
          {llmScripts.map(({ script: name, caption }) => {
            const available = llmTargets.some((t) => t.script === name)
            const dep = llmBlocked.find((u) => u.script === name)
            const why = available
              ? undefined
              : files.length === 0
                ? 'Add a file to see what file type it can be converted to'
                : dep
                  ? blockedReason(dep)
                  : `${name} does not take ${ext || 'this file'}`

            return (
              <div key={name} className="llm-route">
                <span className="tip" data-tip={why}>
                  <button
                    type="button"
                    className={script === name ? 'format selected' : 'format'}
                    disabled={!available}
                    onClick={() => setScript(script === name ? null : name)}
                  >
                    {name}
                  </button>
                </span>
                {caption && <p className="muted note">{caption}</p>}
              </div>
            )
          })}
        </div>
      </aside>

      <main className={tab === 'convert' ? 'compact' : undefined}>
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

          {/* Disabled while converting: the loop keeps working through the files it
              started with, so clearing them mid-batch wouldn't stop their download
              links from still showing up once each one finishes. */}
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
                <button type="button" className="view" onClick={() => setViewing(f)}>
                  View
                </button>
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
            you garbage. Renaming it to <code>{mismatch.actual}</code> will fix it
          </p>
        )}

        {mixedExtensions && (
          <p className="warning">
            Converting and combining both need every file to be the same format,
            and these are {distinctExts.join(', ')}. Remove the odd ones out
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
                  : !runTarget
                    ? missingPick
                    : undefined
            }
          >
            <button
              className="action"
              onClick={() => runTarget && convertAll(runTarget)}
              disabled={files.length === 0 || mixedExtensions || !runTarget || busy}
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
              onClick={combineAll}
              disabled={!canCombine || busy}
            >
              {status.kind === 'combining' ? 'Combining...' : 'Combine Files'}
            </button>
          </span>
        </div>

        <div className="result-actions">
          <button
            type="button"
            onDoubleClick={() => setResult(null)}
            disabled={!result}
          >
            Clear
            <span className="clear-hint">Click twice to clear</span>
          </button>

          <button type="button" onClick={downloadAll} disabled={!result}>
            Download All
          </button>

          {status.kind === 'converting' && (
            <button type="button" onClick={cancelCurrentJob} disabled={cancelling}>
              {cancelling ? 'Cancelling...' : 'Cancel'}
            </button>
          )}
        </div>

        {status.kind === 'converting' && (
          <div className="progress-block">
            <p className="progress-title" title={status.fileName}>
              Converting {status.total > 1 && `${status.position} of ${status.total}: `}
              {status.fileName}.
            </p>
            <ProgressBar percent={percent} queued={queued} />
            <p className="muted progress-time">{formatDuration(elapsed)}</p>
          </div>
        )}

        {result?.downloads.map((d) => (
          <div key={d.url} className="download-row">
            <a className="download" href={d.url} download={d.filename}>
              Download {d.filename}
            </a>
            <button
              type="button"
              className="view"
              onClick={() => setViewing(new File([d.blob], d.filename, { type: d.blob.type }))}
            >
              View
            </button>
            <button
              type="button"
              className="remove"
              onClick={() => removeDownload(d.url)}
              aria-label={`Remove ${d.filename}`}
            >
              &times;
            </button>
          </div>
        ))}

        {status.kind === 'error' && <pre className="error">{status.message}</pre>}
      </main>

      <aside className="log-panel">
        <h2>Result</h2>

        {conversionRuns.map((run) => (
          <section key={run.id} className="log-run">
            {run.files.map((entry) => (
              <div key={entry.id} className={entry.failed ? 'log-entry failed' : 'log-entry'}>
                <p className="log-file" title={entry.fileName}>{entry.fileName}</p>
                {entry.convertedTo && <p className="muted">Converted to {entry.convertedTo}</p>}
                {entry.lines.map((line, i) => (
                  <p key={`${entry.id}-${i}`} className="muted">{line}</p>
                ))}
              </div>
            ))}
          </section>
        ))}

        {history.entries.length > 0 && (
          <section className="history">
            <h3>Recent</h3>
            <ul>
              {history.entries.map((entry) => (
                <li key={entry.id} title={entry.fileName}>{entry.fileName}</li>
              ))}
            </ul>
            <button type="button" onDoubleClick={history.clear}>
              Clear history
              <span className="clear-hint">Click twice to clear</span>
            </button>
          </section>
        )}
      </aside>

      {/* In a portal, so the layout's container query below can't pin the overlay to the
          layout instead of the window. */}
      {viewing && createPortal(<FileViewer file={viewing} onClose={() => setViewing(null)} />, document.body)}
    </div>
  )
}
