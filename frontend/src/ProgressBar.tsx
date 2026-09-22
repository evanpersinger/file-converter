interface ProgressBarProps {
  /** 0 to 100, or null when the backend has no percentage for this conversion. */
  percent: number | null
}

export default function ProgressBar({ percent }: ProgressBarProps) {
  const label = percent === null ? 'Converting...' : `${percent}%`

  return (
    <div
      className={percent === null ? 'progress indeterminate' : 'progress'}
      role="progressbar"
      aria-label="Conversion progress"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent ?? undefined}
    >
      <span className="progress-label">{label}</span>
      {/* The same label again, in inverted colors and clipped to the filled part, so
          the text stays readable on both the filled and the empty side of the bar. */}
      {percent !== null && (
        <div className="progress-fill" style={{ clipPath: `inset(0 ${100 - percent}% 0 0)` }}>
          <span className="progress-label">{label}</span>
        </div>
      )}
    </div>
  )
}
