interface Props {
  value: unknown
  collapsed?: boolean
}

export function JsonViewer({
  value,
  collapsed = false,
}: Props) {
  let text: string
  try {
    text = JSON.stringify(value, null, 2)
  } catch {
    text = String(value)
  }
  if (collapsed) {
    text = text.replace(/\s+/g, ' ').slice(0, 240)
  }
  return (
    <pre className="admin-json-viewer">
      <code>{text}</code>
    </pre>
  )
}
