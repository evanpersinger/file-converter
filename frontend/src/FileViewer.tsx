import { useEffect, useRef, useState } from 'react'
import type { PptxViewer } from '@aiden0z/pptx-renderer'
import { extensionOf } from './api'

interface FileViewerProps {
  file: File
  onClose: () => void
}

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
const TEXT_EXTS = ['.csv', '.txt', '.sql', '.r', '.rmd', '.md', '.ipynb']

// The backend sends every converted file as application/octet-stream, and a browser
// saves that instead of showing it. This already picks how to render by extension, so
// it types the blob by extension too. Anything not listed keeps its own type.
const MIME_TYPES: Partial<Record<string, string>> = {
  '.pdf': 'application/pdf',
  '.svg': 'image/svg+xml',
}

const ZOOM_STEP = 0.1
const MIN_ZOOM = 0.25
const MAX_ZOOM = 3

type PptxStatus =
  | { kind: 'loading' }
  | { kind: 'ready' }
  | { kind: 'error'; message: string }

/**
 * Preview a file before it's converted. Images and PDFs render directly, pptx decks are
 * drawn slide by slide in the browser, plain-text formats (csv, txt, sql, R, md, Rmd,
 * ipynb) show as text. Anything else (docx, xlsx, heic, ...) says so rather than showing
 * nothing.
 */
export default function FileViewer({ file, onClose }: FileViewerProps) {
  const ext = extensionOf(file.name)
  const isImage = IMAGE_EXTS.includes(ext)
  const isPdf = ext === '.pdf'
  const isPptx = ext === '.pptx'
  const isText = TEXT_EXTS.includes(ext)
  const isMarkdown = ext === '.md'

  const [url, setUrl] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null)
  const [pptxStatus, setPptxStatus] = useState<PptxStatus>({ kind: 'loading' })
  const pptxRef = useRef<HTMLDivElement>(null)
  const pptxViewerRef = useRef<PptxViewer | null>(null)
  // Null until the image loads and its natural size is known.
  const [naturalWidth, setNaturalWidth] = useState<number | null>(null)
  // Fraction of natural size, e.g. 1 = 100%. Starts at whatever fits the preview box,
  // computed once the image loads, then +/- step from there. For a pptx it is a fraction
  // of the size that fits the box (1 = a slide fills the width), set once the deck loads.
  const [zoom, setZoom] = useState<number | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isImage && !isPdf) return
    const objectUrl = URL.createObjectURL(file.slice(0, file.size, MIME_TYPES[ext] ?? file.type))
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file, ext, isImage, isPdf])

  useEffect(() => {
    if (!isText) return
    setText(null)
    // A stale read finishing after the file changed must not overwrite the new one.
    let active = true
    file.text().then((content) => {
      if (active) setText(content)
    })
    return () => {
      active = false
    }
  }, [file, isText])

  useEffect(() => {
    const container = pptxRef.current
    if (!isPptx || !container) return
    setPptxStatus({ kind: 'loading' })
    const controller = new AbortController()

    async function render(target: HTMLDivElement) {
      try {
        // Loaded on demand so the renderer and its chart library stay out of the
        // initial bundle for everyone who never previews a deck.
        const [pptx, buffer] = await Promise.all([
          import('@aiden0z/pptx-renderer'),
          file.arrayBuffer(),
        ])
        const viewer = await pptx.PptxViewer.open(buffer, target, {
          // Users upload these, so cap what a hostile zip can unpack to.
          zipLimits: pptx.RECOMMENDED_ZIP_LIMITS,
          listOptions: { windowed: true },
          scrollContainer: target,
          signal: controller.signal,
        })
        if (controller.signal.aborted) {
          viewer.destroy()
          return
        }
        pptxViewerRef.current = viewer
        setZoom(1)
        setPptxStatus({ kind: 'ready' })
      } catch (error) {
        if (controller.signal.aborted) return
        setPptxStatus({
          kind: 'error',
          message: error instanceof Error ? error.message : 'unknown error',
        })
      }
    }
    void render(container)

    return () => {
      controller.abort()
      pptxViewerRef.current?.destroy()
      pptxViewerRef.current = null
    }
  }, [file, isPptx])

  // The renderer scales relative to fitting the box too, so the fraction maps straight
  // onto its percent.
  useEffect(() => {
    const viewer = pptxViewerRef.current
    if (zoom === null || !viewer) return
    const percent = Math.round(zoom * 100)
    if (viewer.zoomPercent !== percent) void viewer.setZoom(percent)
  }, [zoom])

  useEffect(() => {
    setNaturalWidth(null)
    setZoom(null)
  }, [file])

  // The View button that opened this never lost focus, since the overlay just covers
  // it rather than taking focus itself. Closing via a key (Escape) is itself a
  // keyboard event, which flips the browser's focus-ring heuristic back on for that
  // still-focused button, so its focus ring reappears once the overlay unmounts.
  // Blurring on the way out prevents that, regardless of which way it was closed.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      ;(document.activeElement as HTMLElement | null)?.blur()
      onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  function handleClose() {
    ;(document.activeElement as HTMLElement | null)?.blur()
    onClose()
  }

  return (
    <div className="viewer-overlay" onClick={handleClose}>
      {/* Stops a click inside the box from bubbling to the overlay and closing it. */}
      <div className="viewer-box" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-header">
          <span className="viewer-title" title={file.name}>{file.name}</span>

          {(isImage || isPptx) && zoom !== null && (
            <div className="viewer-zoom">
              <button
                type="button"
                className="remove"
                onClick={() => setZoom((z) => Math.max(MIN_ZOOM, (z ?? 1) - ZOOM_STEP))}
                disabled={zoom <= MIN_ZOOM}
                aria-label="Zoom out"
              >
                &minus;
              </button>
              <span>{Math.round(zoom * 100)}%</span>
              <button
                type="button"
                className="remove"
                onClick={() => setZoom((z) => Math.min(MAX_ZOOM, (z ?? 1) + ZOOM_STEP))}
                disabled={zoom >= MAX_ZOOM}
                aria-label="Zoom in"
              >
                +
              </button>
            </div>
          )}

          <button type="button" className="remove" onClick={handleClose} aria-label="Close preview">
            &times;
          </button>
        </div>

        <div className="viewer-body" ref={bodyRef}>
          {isImage && url && (
            <img
              src={url}
              alt={file.name}
              // Fires once the browser knows the image's real pixel size. Fit-to-box
              // never enlarges past that size, only shrinks, so this is also the
              // ceiling for the starting zoom.
              onLoad={(e) => {
                const { naturalWidth: w, naturalHeight: h } = e.currentTarget
                setNaturalWidth(w)
                const box = bodyRef.current?.getBoundingClientRect()
                const fitScale = box ? Math.min(1, box.width / w, box.height / h) : 1
                setZoom(Math.max(MIN_ZOOM, fitScale))
              }}
              style={
                zoom !== null && naturalWidth !== null
                  ? { width: `${naturalWidth * zoom}px`, maxWidth: 'none', maxHeight: 'none' }
                  : undefined
              }
            />
          )}
          {isPdf && url && <iframe src={url} title={file.name} />}
          {isPptx && (
            <div className="pptx-wrap">
              {/* The renderer draws the slides into this div. */}
              <div className="pptx-container" ref={pptxRef} />
              {pptxStatus.kind === 'loading' && <p className="muted pptx-status">Loading...</p>}
              {pptxStatus.kind === 'error' && (
                <p className="muted pptx-status">
                  Could not preview this presentation: {pptxStatus.message}
                </p>
              )}
            </div>
          )}
          {isText && (
            text === null
              ? <p className="muted">Loading...</p>
              : <pre className={isMarkdown ? 'markdown' : undefined}>{text}</pre>
          )}
          {!isImage && !isPdf && !isPptx && !isText && (
            <p className="muted">No preview available for this file type yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
