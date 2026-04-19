import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'

interface LogRow {
  ts_ns: number
  labels: Record<string, string>
  line: string
}

const LEVELS = [
  '',
  'debug',
  'info',
  'warning',
  'error',
  'critical',
]

function fmtTs(ns: number): string {
  return new Date(
    Math.floor(ns / 1_000_000),
  ).toLocaleTimeString()
}

export function LogsRoute() {
  const [container, setContainer] = useState('')
  const [level, setLevel] = useState('')
  const [contains, setContains] = useState('')
  const [minutes, setMinutes] = useState(15)
  const [running, setRunning] = useState(true)
  const { data, refetch, isFetching, error } =
    useQuery({
      queryKey: [
        'admin',
        'logs',
        container,
        level,
        contains,
        minutes,
      ],
      queryFn: () =>
        adminApi.logsQuery({
          container: container || undefined,
          level: level || undefined,
          contains: contains || undefined,
          minutes,
          limit: 500,
        }),
      refetchInterval: running ? 5000 : false,
    })
  const items = (data?.items as LogRow[]) || []

  return (
    <div>
      <h1>Logs</h1>
      <div className="admin-toolbar admin-toolbar--wrap">
        <input
          type="text"
          placeholder="container"
          value={container}
          onChange={(e) =>
            setContainer(e.target.value)
          }
        />
        <select
          value={level}
          onChange={(e) =>
            setLevel(e.target.value)
          }
        >
          {LEVELS.map((l) => (
            <option key={l || 'any'} value={l}>
              {l || 'any level'}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="contains…"
          value={contains}
          onChange={(e) =>
            setContains(e.target.value)
          }
        />
        <select
          value={String(minutes)}
          onChange={(e) =>
            setMinutes(Number(e.target.value))
          }
        >
          <option value="5">5m</option>
          <option value="15">15m</option>
          <option value="60">1h</option>
          <option value="360">6h</option>
          <option value="1440">24h</option>
        </select>
        <Press
          variant="ghost"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          Refresh
        </Press>
        <Press
          variant="ghost"
          onClick={() =>
            setRunning((v) => !v)
          }
        >
          {running ? 'Pause' : 'Resume'}
        </Press>
      </div>
      {error && (
        <div className="admin-error">
          {(error as Error).message}
        </div>
      )}
      <div className="admin-log-stream">
        {items.length === 0 && (
          <div className="admin-log-empty">
            No log entries
          </div>
        )}
        {items.map((row, idx) => (
          <div
            key={`${row.ts_ns}-${idx}`}
            className={`admin-log-row admin-log-row--${
              row.labels?.level || 'info'
            }`}
          >
            <span className="admin-log-ts">
              {fmtTs(row.ts_ns)}
            </span>
            <span className="admin-log-tag">
              {row.labels?.container ||
                row.labels?.service ||
                'log'}
            </span>
            <span className="admin-log-line">
              {row.line}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
