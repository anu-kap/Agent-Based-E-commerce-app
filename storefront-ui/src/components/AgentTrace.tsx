interface Props {
  trace: string[]
}

export function AgentTrace({ trace }: Props) {
  if (!trace.length) return null
  return (
    <details className="trace">
      <summary>Agent trace</summary>
      {trace.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </details>
  )
}
