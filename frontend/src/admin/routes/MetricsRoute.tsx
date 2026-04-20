import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../lib/adminApi'
import {
  ChartPoint,
  LineChart,
} from '../components/charts/LineChart'

interface PromRange {
  data?: {
    result?: Array<{
      values: Array<[number, string]>
    }>
  }
}

function flatten(raw: unknown): ChartPoint[] {
  const data = raw as PromRange
  const series = data?.data?.result?.[0]?.values
  if (!series) return []
  return series.map(([ts, value]) => ({
    ts,
    value: Number(value),
  }))
}

export function MetricsRoute() {
  const { t } = useTranslation()
  const [minutes, setMinutes] = useState(60)
  const list = useQuery({
    queryKey: ['admin', 'metrics', 'list'],
    queryFn: () => adminApi.metricsList(),
  })
  const rps = useQuery({
    queryKey: ['admin', 'metrics', 'rps', minutes],
    queryFn: () =>
      adminApi.metricRange('rps_5m', minutes, 30),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const errs = useQuery({
    queryKey: ['admin', 'metrics', 'err', minutes],
    queryFn: () =>
      adminApi.metricRange(
        'error_rate_5m',
        minutes,
        30,
      ),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const lat = useQuery({
    queryKey: ['admin', 'metrics', 'lat', minutes],
    queryFn: () =>
      adminApi.metricRange(
        'latency_p95_5m',
        minutes,
        30,
      ),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const srcStatus =
    (rps.data as any)?.source_status ??
    (errs.data as any)?.source_status ??
    (lat.data as any)?.source_status
  const srcReason =
    (rps.data as any)?.source_reason ??
    (errs.data as any)?.source_reason ??
    (lat.data as any)?.source_reason

  return (
    <div>
      <h1>{t('admin.metrics.title')}</h1>
      <div className="admin-toolbar">
        <select
          value={String(minutes)}
          onChange={(e) =>
            setMinutes(Number(e.target.value))
          }
        >
          <option value="15">15m</option>
          <option value="60">1h</option>
          <option value="360">6h</option>
          <option value="1440">24h</option>
        </select>
        <span className="admin-card__sub">
          {t('admin.metrics.available', {
            count: list.data?.metrics.length ?? 0,
          })}
        </span>
      </div>
      {srcStatus === 'disabled' && (
        <div className="admin-warning">
          {t('admin.metrics.sourceDisabled', {
            defaultValue:
              'Prometheus не настроен или observability-стек не поднят. Запустите docker compose -f docker-compose.observability.yml up -d.',
          })}
        </div>
      )}
      {srcStatus === 'error' && (
        <div className="admin-error">
          {t('admin.metrics.sourceError', {
            defaultValue: 'Prometheus недоступен: {{reason}}',
            reason: String(srcReason ?? ''),
          })}
        </div>
      )}
      <section className="admin-card">
        <h2>{t('admin.metrics.rps')}</h2>
        <LineChart
          data={flatten(rps.data)}
          ariaLabel="Requests per second"
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.metrics.errorRate')}</h2>
        <LineChart
          data={flatten(errs.data)}
          ariaLabel="HTTP error rate"
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.metrics.latency')}</h2>
        <LineChart
          data={flatten(lat.data)}
          ariaLabel="Latency p95"
        />
      </section>
    </div>
  )
}
