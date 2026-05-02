import type { Automation } from '../types/api'

interface Props {
  automation: Automation
}

export function AutomationStatus({ automation }: Props) {
  if (!automation?.kestra) return null
  const { kestra } = automation
  return (
    <div className="automation-status">
      <strong>{kestra.status === 'triggered' ? 'Kestra workflow started' : 'Kestra workflow ready'}</strong>
      <span>{kestra.executionId ? `Execution ${kestra.executionId}` : 'Start Kestra locally to execute this workflow.'}</span>
      {kestra.url && (
        <a href={kestra.url} target="_blank" rel="noreferrer">
          Open Kestra
        </a>
      )}
    </div>
  )
}
