import { useEffect, useState } from 'react'
import { extensionOf } from './api'

interface FileViewerProps {
  file: File
  onClose: () => void
}

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
const TEXT_EXTS = ['.csv', '.txt', '.sql', '.r', '.rmd', '.md', '.ipynb']

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
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="viewer-overlay" onClick={onClose}>
      {/* Stops a click inside the box from bubbling to the overlay and closing it. */}
      <div className="viewer-box" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-header">
          <span className="viewer-title" title={file.name}>{file.name}</span>
          <button type="button" className="remove" onClick={onClose} aria-label="Close preview">
            &times;
          </button>
        </div>

        <div className="viewer-body">
          {isImage && url && <img src={url} alt={file.name} />}
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
