import { useEffect, useRef, useState } from 'react'
import { extensionOf } from './api'

interface FileViewerProps {
  file: File
  onClose: () => void
}

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
const TEXT_EXTS = ['.csv', '.txt', '.sql', '.r', '.rmd', '.md', '.ipynb']

const ZOOM_STEP = 0.1
const MIN_ZOOM = 0.25
const MAX_ZOOM = 3

/**
 * Preview a file before it's converted. Images and PDFs render directly, plain-text
 * formats (csv, txt, sql, R, md, Rmd, ipynb) show as text. Anything else (docx, pptx,
 * xlsx, heic, ...) says so rather than showing nothing.
 */
export default function FileViewer({ file, onClose }: FileViewerProps) {
  const ext = extensionOf(file.name)
  const isImage = IMAGE_EXTS.includes(ext)
  const isPdf = ext === '.pdf'
  const isText = TEXT_EXTS.includes(ext)

  const [url, setUrl] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null)
  // Null until the image loads and its natural size is known.
  const [naturalWidth, setNaturalWidth] = useState<number | null>(null)
  // Fraction of natural size, e.g. 1 = 100%. Starts at whatever fits the preview box,
  // computed once the image loads, then +/- step from there.
  const [zoom, setZoom] = useState<number | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isImage && !isPdf) return
    const objectUrl = URL.createObjectURL(file)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file, isImage, isPdf])

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

          {isImage && zoom !== null && (
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
          {isText && (text === null ? <p className="muted">Loading...</p> : <pre>{text}</pre>)}
          {!isImage && !isPdf && !isText && (
            <p className="muted">No preview available for this file type yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
