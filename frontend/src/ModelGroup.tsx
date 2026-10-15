import type { ModelGroupData } from './types'

interface ModelGroupProps {
  group: ModelGroupData
  // The name of the picked model when it belongs to this group, null otherwise.
  picked: string | null
  onPick: (name: string) => void
}

/** A headed list of model buttons. The model picker is one of these per provider. */
export default function ModelGroup({ group, picked, onPick }: ModelGroupProps) {
  return (
    <div className="model-group">
      <p className="muted">{group.title}</p>

      {group.message && <p className="muted">{group.message}</p>}

      {group.models.map((m) => (
        <span key={m.name} className="tip" data-tip={m.blocked}>
          <button
            type="button"
            className={picked === m.name ? 'format selected' : 'format'}
            disabled={m.blocked !== undefined}
            title={m.name}
            onClick={() => onPick(m.name)}
          >
            {m.label ?? m.name}
          </button>
        </span>
      ))}
    </div>
  )
}
