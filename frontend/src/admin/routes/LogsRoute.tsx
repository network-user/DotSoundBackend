import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { MotionPress } from '@/components/ui/MotionPress'
import { adminApi } from '../lib/adminApi'
import { LiveLogStream } from '../components/widgets/LiveLogStream'

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
  const { t } = useTranslation()
  const [mode, setMode] = useState<'live' | 'history'>(
    'live',
  )
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
      refetchInterval: running ? 15_000 : false,
      refetchIntervalInBackground: false,
    })
  const items = (data?.items as LogRow[]) || []

  if (mode === 'live') {
    return (
      <div>
        <h1>{t('admin.logs.title')}</h1>
        <div className="admin-toolbar">
          <MotionPress
            variant="ghost"
            onClick={() => setMode('history')}
          >
            {t('admin.logs.switchHistory')}
          </MotionPress>
        </div>
        <LiveLogStream />
      </div>
    )
  }

  return (
    <div>
      <h1>{t('admin.logs.title')}</h1>
      <div className="admin-toolbar">
        <MotionPress
          variant="ghost"
          onClick={() => setMode('live')}
        >
          {t('admin.logs.switchLive')}
        </MotionPress>
      </div>
      <div className="admin-toolbar admin-toolbar--wrap">
        <input
          type="text"
          placeholder={t(
            'admin.logs.containerPlaceholder',
          )}
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
              {l || t('admin.logs.anyLevel')}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder={t(
            'admin.logs.containsPlaceholder',
          )}
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
        <MotionPress
          variant="ghost"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          {t('admin.logs.refresh')}
        </MotionPress>
        <MotionPress
          variant="ghost"
          onClick={() =>
            setRunning((v) => !v)
          }
        >
          {running
            ? t('admin.logs.pause')
            : t('admin.logs.resume')}
        </MotionPress>
      </div>
      {error && (
        <div className="admin-error">
          {(error as Error).message}
        </div>
      )}
      {(data as { source_status?: string })?.source_status ===
        'local_dev' && (
        <div className="admin-card__sub">
          {t('admin.logs.sourceLocalDev', {
            defaultValue:
              'Local dev: log files in DOTSOUND_DEV_LOG_DIR (backend.log, bot.log, compute-worker.log).',
          })}
        </div>
      )}
      {(data as { source_status?: string })?.source_status ===
        'disabled' && (
        <div className="admin-warning">
          {t('admin.logs.sourceDisabled', {
            defaultValue:
              'Loki не настроен или observability-стек не поднят. Запустите docker compose -f docker-compose.observability.yml up -d. Для dev без Loki: задайте DOTSOUND_DEV_LOG_DIR и дублируйте логи в файлы (см. docs/admin/README).',
          })}
        </div>
      )}
      {(data as any)?.source_status === 'error' && (
        <div className="admin-error">
          {t('admin.logs.sourceError', {
            defaultValue: 'Loki недоступен: {{reason}}',
            reason: String((data as any)?.source_reason ?? ''),
          })}
        </div>
      )}
      <div className="admin-log-stream">
        {items.length === 0 && (
          <div className="admin-log-empty">
            {t('admin.logs.empty')}
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
