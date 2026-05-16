import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ImportDiagnosticEntry } from '../../types/api'

interface Props {
  entries: ImportDiagnosticEntry[] | undefined
  defaultOpen?: boolean
}

function statusBadgeColor(entry: ImportDiagnosticEntry): string {
  if (entry.ok) return 'var(--c-accent, #4caf50)'
  if (entry.status === 0) return 'var(--c-warning, #ff9800)'
  if (entry.status >= 500) return 'var(--c-danger, #f44336)'
  if (entry.status === 451) return 'var(--c-warning, #ff9800)'
  if (entry.status >= 400) return 'var(--c-danger, #f44336)'
  return 'var(--c-muted, #888)'
}

function shortenUrl(url: string): string {
  try {
    const u = new URL(url)
    return u.pathname + (u.search ? u.search : '')
  } catch {
    return url
  }
}

export function ImportDiagnosticsPanel({
  entries,
  defaultOpen = false,
}: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)
  const list = entries ?? []
  if (list.length === 0) return null

  return (
    <details
      className="import-diagnostics"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{
        margin: '12px 16px',
        padding: '8px 12px',
        border: '1px solid var(--c-border, #2a2a2a)',
        borderRadius: 8,
        background: 'var(--c-bg-subtle, rgba(255,255,255,0.02))',
      }}
    >
      <summary
        style={{
          cursor: 'pointer',
          userSelect: 'none',
          fontWeight: 500,
          fontSize: 13,
          opacity: 0.85,
        }}
      >
        {t('import.diagnosticsTitle', {
          defaultValue: 'Provider requests',
          count: list.length,
        })}{' '}
        ({list.length})
      </summary>
      <ul
        style={{
          listStyle: 'none',
          margin: '8px 0 0',
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          fontFamily:
            'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
          fontSize: 12,
        }}
      >
        {list.map((e, i) => (
          <li
            key={i}
            style={{
              padding: '6px 8px',
              borderRadius: 6,
              background: 'rgba(255,255,255,0.03)',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
              }}
            >
              <span
                style={{
                  display: 'inline-block',
                  minWidth: 36,
                  textAlign: 'center',
                  padding: '1px 6px',
                  borderRadius: 4,
                  background: statusBadgeColor(e),
                  color: '#fff',
                  fontWeight: 600,
                }}
              >
                {e.status === 0 ? 'ERR' : e.status}
              </span>
              <span style={{ opacity: 0.6 }}>{e.method}</span>
              <span style={{ opacity: 0.6 }}>{e.stage}</span>
              <span
                style={{
                  marginLeft: 'auto',
                  opacity: 0.5,
                  fontSize: 11,
                }}
              >
                {e.elapsed_ms} ms
              </span>
            </div>
            <div
              style={{
                opacity: 0.85,
                wordBreak: 'break-all',
                fontSize: 11,
              }}
              title={e.url}
            >
              {shortenUrl(e.url)}
            </div>
            {e.error && (
              <div
                style={{
                  color: 'var(--c-danger, #f44336)',
                  wordBreak: 'break-word',
                  whiteSpace: 'pre-wrap',
                  fontSize: 11,
                  opacity: 0.95,
                }}
              >
                {e.error}
              </div>
            )}
          </li>
        ))}
      </ul>
    </details>
  )
}
