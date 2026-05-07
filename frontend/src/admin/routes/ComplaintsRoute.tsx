import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { AnimatePresence } from 'framer-motion'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { showIsland } from '@/lib/island'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { KpiCard } from '../components/widgets/KpiCard'
import { Sparkline } from '../components/charts/Sparkline'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'

interface ComplaintRow {
  id: number
  track_id: number
  reason: string
  reason_type: string
  is_resolved: boolean
  created_at: string
}

async function resolveAction(
  id: number,
  action: 'accept' | 'dismiss' | 'in_progress',
  note?: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    await api.updateComplaintStatus(id, {
      action,
      note,
    })
    return { ok: true }
  } catch (e) {
    const msg = e instanceof Error ? e.message : '0'
    if (msg === '404') {
      return { ok: false, error: 'not_implemented' }
    }
    return { ok: false, error: msg }
  }
}

export function ComplaintsRoute() {
  const { t } = useTranslation()
  const { showConfirm } = useAdminPrompt()
  const queryClient = useQueryClient()
  const reduce = useReducedMotion()
  const [page, setPage] = useState(1)
  const [unresolvedOnly, setUnresolvedOnly] =
    useState(true)
  const [acceptNote, setAcceptNote] = useState('')
  const [rejectNote, setRejectNote] = useState('')
  const [busyId, setBusyId] = useState<number | null>(
    null,
  )

  const queryKey = [
    'admin',
    'complaints',
    page,
    unresolvedOnly,
  ] as const

  const { data, isFetching } = useQuery({
    queryKey,
    queryFn: () =>
      adminApi.listComplaints({
        page,
        size: 25,
        unresolved_only: unresolvedOnly,
      }),
    placeholderData: keepPreviousData,
  })

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey })

  const rows =
    (data?.items || []) as unknown as ComplaintRow[]

  const unresolvedSorted = useMemo(() => {
    return rows
      .filter((r) => !r.is_resolved)
      .slice()
      .sort(
        (a, b) =>
          new Date(a.created_at).getTime() -
          new Date(b.created_at).getTime(),
      )
  }, [rows])

  const current = unresolvedSorted[0] ?? null

  const trackMeta = useQuery({
    queryKey: ['admin', 'complaint-track', current?.track_id],
    queryFn: () => api.getTrack(current!.track_id),
    enabled: Boolean(current?.track_id),
  })

  async function runResolve(
    complaint: ComplaintRow,
    action: 'accept' | 'dismiss' | 'in_progress',
  ) {
    setBusyId(complaint.id)
    try {
      const note =
        action === 'accept'
          ? acceptNote.trim() || undefined
          : action === 'dismiss'
            ? rejectNote.trim() || undefined
            : undefined
      const res = await resolveAction(
        complaint.id,
        action,
        note,
      )
      if (!res.ok && res.error === 'not_implemented') {
        showIsland({
          kind: 'error',
          title: t('redesign.admin.complaintEndpointMissing'),
          durationMs: 5000,
        })
        return
      }
      if (!res.ok) {
        showIsland({
          kind: 'error',
          title: t('redesign.admin.complaintActionFailed'),
          hint: res.error ?? '',
          durationMs: 4500,
        })
        return
      }
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.complaintSaved'),
        durationMs: 2400,
      })
      setAcceptNote('')
      setRejectNote('')
      refresh()
    } finally {
      setBusyId(null)
    }
  }

  async function handleAccept(c: ComplaintRow) {
    await runResolve(c, 'accept')
  }

  async function handleDismiss(c: ComplaintRow) {
    const ok = await showConfirm(
      t('redesign.admin.complaintDismissConfirm'),
      { danger: true },
    )
    if (!ok) return
    await runResolve(c, 'dismiss')
  }

  async function handleProgress(c: ComplaintRow) {
    await runResolve(c, 'in_progress')
  }

  const columns: ColumnDef<ComplaintRow>[] = [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<number>()}
        </span>
      ),
    },
    { header: 'Track', accessorKey: 'track_id' },
    { header: 'Reason', accessorKey: 'reason' },
    { header: 'Type', accessorKey: 'reason_type' },
    {
      header: 'Status',
      cell: (i) =>
        i.row.original.is_resolved ? (
          <StatusPill kind="ok">resolved</StatusPill>
        ) : (
          <StatusPill kind="warn">open</StatusPill>
        ),
    },
    {
      header: 'Created',
      cell: (i) =>
        new Date(
          i.row.original.created_at,
        ).toLocaleString(),
    },
  ]

  const total = data?.total || 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )
  const openCount = rows.filter((r) => !r.is_resolved).length
  const resolvedCount = rows.filter(
    (r) => r.is_resolved,
  ).length
  const sparkline = useMemo(() => {
    const buckets = new Map<string, number>()
    for (const row of rows) {
      const day = new Date(row.created_at)
        .toISOString()
        .slice(0, 10)
      buckets.set(day, (buckets.get(day) || 0) + 1)
    }
    return Array.from(buckets.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, value]) => value)
  }, [rows])

  const stepTransition = reduce ? TWEEN_FAST : SPRING_GENTLE

  return (
    <div>
      <h1>{t('admin.complaints.title')}</h1>

      <section className="adm-r-complaint-queue glass--medium admin-card">
        <h2 className="adm-r-complaint-queue__title">
          {t('redesign.admin.complaintQueueTitle')}
        </h2>
        <p className="admin-card__sub">
          {t('redesign.admin.complaintQueueHint')}
        </p>
        <AnimatePresence mode="wait">
          {current ? (
            <m.div
              key={current.id}
              className="adm-r-complaint-queue__card"
              initial={
                reduce
                  ? false
                  : { opacity: 0, y: 16 }
              }
              animate={{ opacity: 1, y: 0 }}
              exit={
                reduce
                  ? undefined
                  : { opacity: 0, y: -12 }
              }
              transition={stepTransition}
            >
              <div className="adm-r-complaint-queue__head">
                <span className="admin-mono">
                  #{current.id}
                </span>
                <span>
                  {t('redesign.admin.complaintTrack')}{' '}
                  {current.track_id}
                </span>
              </div>
              {trackMeta.data && (
                <p className="adm-r-complaint-queue__track-title">
                  {trackMeta.data.title}
                  {trackMeta.data.artist
                    ? ` — ${trackMeta.data.artist}`
                    : ''}
                </p>
              )}
              <p className="adm-r-complaint-queue__reason">
                {current.reason}
              </p>
              <div className="adm-r-complaint-queue__chips">
                <span className="glass--medium adm-r-chip">
                  {current.reason_type}
                </span>
                <span className="glass--medium adm-r-chip">
                  {new Date(
                    current.created_at,
                  ).toLocaleString()}
                </span>
              </div>
              <label className="adm-r-complaint-queue__label">
                {t('redesign.admin.complaintAcceptNote')}
                <textarea
                  className="adm-r-complaint-queue__textarea"
                  rows={2}
                  value={acceptNote}
                  onChange={(e) =>
                    setAcceptNote(e.target.value)
                  }
                  disabled={busyId !== null}
                />
              </label>
              <label className="adm-r-complaint-queue__label">
                {t('redesign.admin.complaintRejectNote')}
                <textarea
                  className="adm-r-complaint-queue__textarea"
                  rows={2}
                  value={rejectNote}
                  onChange={(e) =>
                    setRejectNote(e.target.value)
                  }
                  disabled={busyId !== null}
                />
              </label>
              <div className="adm-r-complaint-queue__actions">
                <MotionPress
                  variant="primary"
                  disabled={busyId !== null}
                  onClick={() => void handleAccept(current)}
                >
                  {busyId === current.id
                    ? t('admin.common.loading')
                    : t('redesign.admin.complaintAccept')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  disabled={busyId !== null}
                  onClick={() =>
                    void handleDismiss(current)
                  }
                >
                  {t('redesign.admin.complaintReject')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  disabled={busyId !== null}
                  onClick={() =>
                    void handleProgress(current)
                  }
                >
                  {t('redesign.admin.complaintProgress')}
                </MotionPress>
              </div>
            </m.div>
          ) : (
            <m.p
              key="empty"
              className="adm-r-complaint-queue__empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {t('redesign.admin.complaintQueueEmpty')}
            </m.p>
          )}
        </AnimatePresence>
      </section>

      <section className="kpi-grid adm-r-kpi-stagger">
        <KpiCard
          label={t('admin.complaints.title')}
          value={total}
          hint={t('admin.common.total', { count: total })}
        />
        <KpiCard
          label={t('redesign.admin.complaintKpiOpen')}
          value={openCount}
          accent={openCount > 0 ? 'warn' : 'default'}
        />
        <KpiCard
          label={t('redesign.admin.complaintKpiResolved')}
          value={resolvedCount}
          hint={
            sparkline.length > 1 ? (
              <Sparkline
                data={sparkline}
                ariaLabel={t(
                  'redesign.admin.complaintSparklineAria',
                )}
              />
            ) : undefined
          }
        />
      </section>
      <div className="admin-toolbar adm-r-toolbar-sticky">
        <label className="admin-checkbox">
          <input
            type="checkbox"
            checked={unresolvedOnly}
            onChange={(e) => {
              setUnresolvedOnly(
                e.target.checked,
              )
              setPage(1)
            }}
          />
          {t('admin.complaints.unresolvedOnly')}
        </label>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
      />
      <div className="admin-pagination">
        <MotionPress
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() =>
            setPage((p) => Math.max(1, p - 1))
          }
        >
          {t('admin.common.prev')}
        </MotionPress>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <MotionPress
          variant="ghost"
          disabled={
            page >= totalPages || isFetching
          }
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </MotionPress>
      </div>
    </div>
  )
}
