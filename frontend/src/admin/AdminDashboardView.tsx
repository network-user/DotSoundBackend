import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

type Stats = {
  workersOnline: number
  jobsQueued: number
  jobsDone24h: number
}

export function AdminDashboardView() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const workers: Array<{ active?: boolean }> =
          await api
            .getAdminManifest()
            .then(() =>
              fetch('/api/v1/admin/audio-compute/workers', {
                headers: authHeader(),
              }).then((r) =>
                r.ok ? r.json() : [],
              ),
            )
        const jobs: Array<{ status?: string; finished_at?: string }> =
          await fetch('/api/v1/admin/audio-compute/jobs', {
            headers: authHeader(),
          }).then((r) => (r.ok ? r.json() : []))
        if (cancelled) return
        const queued = jobs.filter(
          (j) => j.status === 'queued',
        ).length
        const dayAgo = Date.now() - 24 * 3600 * 1000
        const done24h = jobs.filter(
          (j) =>
            j.status === 'done' &&
            j.finished_at &&
            new Date(j.finished_at).getTime() > dayAgo,
        ).length
        setStats({
          workersOnline: workers.filter(
            (w) => w.active,
          ).length,
          jobsQueued: queued,
          jobsDone24h: done24h,
        })
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'load failed',
          )
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div className="admin-view">
        <p className="admin-error">{error}</p>
      </div>
    )
  }

  return (
    <div className="admin-view">
      <h1 className="admin-view-title">Dashboard</h1>
      <div className="admin-kpi-grid">
        <KpiCard
          label="Workers online"
          value={stats?.workersOnline ?? '—'}
        />
        <KpiCard
          label="Jobs queued"
          value={stats?.jobsQueued ?? '—'}
        />
        <KpiCard
          label="Completed 24h"
          value={stats?.jobsDone24h ?? '—'}
        />
      </div>
    </div>
  )
}

function KpiCard({
  label,
  value,
}: {
  label: string
  value: number | string
}) {
  return (
    <div className="admin-kpi-card">
      <div className="admin-kpi-label">{label}</div>
      <div className="admin-kpi-value">{value}</div>
    </div>
  )
}

function authHeader(): Record<string, string> {
  const token = localStorage.getItem('auth-token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
