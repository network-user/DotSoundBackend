import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  adminApi,
  type LyricsTimecodeSyncJob,
} from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { AdminRangeSwitch } from '../components/widgets/AdminRangeSwitch'
import { getAdminPanelRoute } from '@/lib/adminPath'

type PanelTab = 'queue' | 'enqueue'
type SinceFilter = 'all' | '24' | '168'

function jobStatusKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'done' || status === 'succeeded') {
    return 'ok'
  }
  if (
    status === 'failed' ||
    status === 'error' ||
    status === 'cancelled'
  ) {
    return 'error'
  }
  if (status === 'queued' || status === 'running') {
    return 'warn'
  }
  return 'unknown'
}

function trackLabel(job: LyricsTimecodeSyncJob): string {
  const title = job.track_title?.trim() || `#${job.track_id}`
  const artist = job.track_artist?.trim()
  return artist ? `${artist} — ${title}` : title
}

function QueueJobCard({
  job,
  badge,
}: {
  job: LyricsTimecodeSyncJob
  badge: string
}) {
  const { t } = useTranslation()
  return (
    <div className="admin-bg-detail__block">
      <span className="admin-card__sub">{badge}</span>
      <div className="admin-mono" style={{ marginTop: 4 }}>
        {trackLabel(job)}
      </div>
      <div
        className="admin-toolbar"
        style={{ marginTop: 8, gap: 8 }}
      >
        <StatusPill kind={jobStatusKind(job.status)}>
          {job.status}
        </StatusPill>
        <span className="admin-card__sub">
          {t('admin.timecodeSync.jobId', {
            id: job.id.slice(0, 10),
          })}
        </span>
        {job.current_tier && (
          <span className="admin-card__sub">
            {job.current_tier}
          </span>
        )}
      </div>
    </div>
  )
}

function PriorityControls({
  job,
  disabled,
  onBump,
  onApply,
}: {
  job: LyricsTimecodeSyncJob
  disabled: boolean
  onBump: () => void
  onApply: (priority: number) => void
}) {
  const { t } = useTranslation()
  const [pri, setPri] = useState(
    () => job.queue_priority ?? 0,
  )
  return (
    <div
      className="admin-toolbar"
      style={{ flexWrap: 'wrap', gap: 6 }}
    >
      <input
        type="number"
        aria-label={t('admin.timecodeSync.priorityInput')}
        value={pri}
        onChange={(e) =>
          setPri(Number(e.target.value))
        }
        disabled={disabled}
        style={{ width: 72 }}
      />
      <MotionPress
        variant="ghost"
        disabled={disabled}
        onClick={() => onApply(pri)}
      >
        {t('admin.timecodeSync.applyPriority')}
      </MotionPress>
      <MotionPress
        variant="primary"
        disabled={disabled}
        onClick={onBump}
      >
        {t('admin.timecodeSync.bumpNext')}
      </MotionPress>
    </div>
  )
}

export function TimecodeSyncRoute() {
  const { t } = useTranslation()
  const { showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const tracksRoute = getAdminPanelRoute('/tracks')
  const [tab, setTab] = useState<PanelTab>('queue')
  const [enqueueLimit, setEnqueueLimit] = useState(100)
  const [trackIdsRaw, setTrackIdsRaw] = useState('')
  const [filterMine, setFilterMine] = useState(false)
  const [sinceFilter, setSinceFilter] =
    useState<SinceFilter>('all')

  const queueParams = useMemo(
    () => ({
      mine: filterMine || undefined,
      since_hours:
        sinceFilter === 'all'
          ? undefined
          : Number(sinceFilter),
    }),
    [filterMine, sinceFilter],
  )

  const queue = useQuery({
    queryKey: [
      'admin',
      'timecode-sync',
      'queue',
      queueParams,
    ],
    queryFn: () =>
      adminApi.lyricsTimecodeSyncQueue(queueParams),
    refetchInterval: tab === 'queue' ? 4000 : false,
  })

  const enqueueMutation = useMutation({
    mutationFn: (body: {
      track_ids?: number[]
      enqueue_all_unsynced?: boolean
      limit?: number
    }) => adminApi.lyricsTimecodeSyncEnqueue(body),
    onSuccess: (res) => {
      showAlert(
        t('admin.timecodeSync.enqueueDone', {
          enqueued: res.enqueued,
          skipped: res.skipped,
          requested: res.requested,
        }),
      )
      qc.invalidateQueries({
        queryKey: ['admin', 'timecode-sync', 'queue'],
      })
      setTab('queue')
    },
    onError: (err: Error) => showAlert(err.message),
  })

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) =>
      adminApi.lyricsTimecodeSyncCancelJob(jobId),
    onSuccess: () => {
      showAlert(t('admin.timecodeSync.cancelDone'))
      qc.invalidateQueries({
        queryKey: ['admin', 'timecode-sync', 'queue'],
      })
    },
    onError: (err: Error) => showAlert(err.message),
  })

  const priorityMutation = useMutation({
    mutationFn: (args: {
      jobId: string
      body: { queue_priority?: number; bump_next?: boolean }
    }) =>
      adminApi.lyricsTimecodeSyncSetPriority(
        args.jobId,
        args.body,
      ),
    onSettled: () =>
      qc.invalidateQueries({
        queryKey: ['admin', 'timecode-sync', 'queue'],
      }),
    onError: (err: Error) => showAlert(err.message),
  })

  const parsedTrackIds = useMemo(() => {
    const ids = trackIdsRaw
      .split(/[\s,;]+/)
      .map((s) => Number.parseInt(s.trim(), 10))
      .filter((n) => Number.isFinite(n) && n > 0)
    return [...new Set(ids)]
  }, [trackIdsRaw])

  const queuedColumns: ColumnDef<LyricsTimecodeSyncJob>[] =
    useMemo(
      () => [
        {
          header: t('admin.timecodeSync.colTrack'),
          id: 'track',
          cell: (i) => trackLabel(i.row.original),
        },
        {
          header: t('admin.timecodeSync.colPriority'),
          accessorKey: 'queue_priority',
        },
        {
          header: t('admin.timecodeSync.colStatus'),
          accessorKey: 'status',
          cell: (i) => (
            <StatusPill
              kind={jobStatusKind(
                i.row.original.status,
              )}
            >
              {i.row.original.status}
            </StatusPill>
          ),
        },
        {
          header: t('admin.timecodeSync.colActions'),
          id: 'actions',
          cell: (i) => {
            const st = i.row.original.status
            const canCancel =
              st === 'queued' || st === 'running'
            return (
              <div
                className="admin-toolbar"
                style={{ flexWrap: 'wrap', gap: 6 }}
              >
                <PriorityControls
                  job={i.row.original}
                  disabled={
                    priorityMutation.isPending ||
                    cancelMutation.isPending
                  }
                  onBump={() =>
                    priorityMutation.mutate({
                      jobId: i.row.original.id,
                      body: { bump_next: true },
                    })
                  }
                  onApply={(queue_priority) =>
                    priorityMutation.mutate({
                      jobId: i.row.original.id,
                      body: { queue_priority },
                    })
                  }
                />
                {canCancel && (
                  <MotionPress
                    variant="ghost"
                    disabled={cancelMutation.isPending}
                    onClick={() =>
                      cancelMutation.mutate(
                        i.row.original.id,
                      )
                    }
                  >
                    {t('admin.timecodeSync.cancelJob')}
                  </MotionPress>
                )}
              </div>
            )
          },
        },
      ],
      [
        t,
        priorityMutation.isPending,
        cancelMutation.isPending,
      ],
    )

  const recentColumns: ColumnDef<LyricsTimecodeSyncJob>[] =
    useMemo(
      () => [
        {
          header: t('admin.timecodeSync.colTrack'),
          id: 'track',
          cell: (i) => trackLabel(i.row.original),
        },
        {
          header: t('admin.timecodeSync.colStatus'),
          accessorKey: 'status',
          cell: (i) => (
            <StatusPill
              kind={jobStatusKind(
                i.row.original.status,
              )}
            >
              {i.row.original.status}
            </StatusPill>
          ),
        },
        {
          header: t('admin.timecodeSync.colFinished'),
          accessorKey: 'finished_at',
          cell: (i) =>
            i.row.original.finished_at
              ? new Date(
                  i.row.original.finished_at,
                ).toLocaleString()
              : '–',
        },
        {
          header: t('admin.timecodeSync.colError'),
          accessorKey: 'error',
          cell: (i) =>
            i.row.original.error ? (
              <span
                className="admin-card__sub"
                title={i.row.original.error}
              >
                {i.row.original.error.slice(0, 80)}
              </span>
            ) : (
              '–'
            ),
        },
      ],
      [t],
    )

  const data = queue.data
  const busy = enqueueMutation.isPending

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <h1>{t('admin.timecodeSync.title')}</h1>
          <p className="admin-card__sub">
            {t('admin.timecodeSync.subtitle')}
          </p>
        </div>
        <Link
          to={tracksRoute}
          className="admin-card__sub"
        >
          {t('admin.timecodeSync.backToTracks')}
        </Link>
      </header>

      <AdminRangeSwitch
        groupId="admin-timecode-sync-tab"
        value={tab}
        onChange={(v) => setTab(v as PanelTab)}
        options={[
          {
            value: 'queue',
            label: t('admin.timecodeSync.tabQueue'),
          },
          {
            value: 'enqueue',
            label: t('admin.timecodeSync.tabEnqueue'),
          },
        ]}
      />

      {tab === 'enqueue' && (
        <section className="admin-card">
          <p className="admin-card__sub">
            {t('admin.timecodeSync.candidatesHint', {
              count: data?.candidate_count ?? '…',
            })}
          </p>
          <div className="admin-toolbar">
            <label className="admin-card__sub">
              {t('admin.timecodeSync.limitLabel')}
              <input
                type="number"
                min={1}
                max={500}
                value={enqueueLimit}
                onChange={(e) =>
                  setEnqueueLimit(
                    Number(e.target.value) || 100,
                  )
                }
                style={{ marginLeft: 8, width: 88 }}
              />
            </label>
          </div>
          <div
            className="admin-toolbar"
            style={{ marginTop: 12 }}
          >
            <MotionPress
              variant="primary"
              disabled={busy}
              onClick={() =>
                enqueueMutation.mutate({
                  enqueue_all_unsynced: true,
                  limit: enqueueLimit,
                })
              }
            >
              {t('admin.timecodeSync.enqueueAll')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              disabled={
                busy || parsedTrackIds.length === 0
              }
              onClick={() =>
                enqueueMutation.mutate({
                  track_ids: parsedTrackIds,
                  limit: enqueueLimit,
                })
              }
            >
              {t('admin.timecodeSync.enqueueIds', {
                count: parsedTrackIds.length,
              })}
            </MotionPress>
          </div>
          <label
            className="admin-card__sub"
            style={{
              display: 'block',
              marginTop: 16,
            }}
          >
            {t('admin.timecodeSync.idsLabel')}
            <textarea
              className="admin-textarea"
              rows={4}
              value={trackIdsRaw}
              onChange={(e) =>
                setTrackIdsRaw(e.target.value)
              }
              placeholder={t(
                'admin.timecodeSync.idsPlaceholder',
              )}
              style={{ marginTop: 8, width: '100%' }}
            />
          </label>
        </section>
      )}

      {tab === 'queue' && (
        <>
          {queue.isError && (
            <p className="admin-error" role="alert">
              {t('admin.timecodeSync.loadFailed')}
            </p>
          )}
          <section className="admin-card">
            <div
              className="admin-toolbar"
              style={{ flexWrap: 'wrap', gap: 12 }}
            >
              <label
                className="admin-card__sub"
                style={{
                  display: 'inline-flex',
                  gap: 6,
                  alignItems: 'center',
                }}
              >
                <input
                  type="checkbox"
                  checked={filterMine}
                  onChange={(e) =>
                    setFilterMine(e.target.checked)
                  }
                />
                {t('admin.timecodeSync.filterMine')}
              </label>
              <AdminRangeSwitch
                groupId="admin-timecode-since"
                value={sinceFilter}
                onChange={(v) =>
                  setSinceFilter(v as SinceFilter)
                }
                options={[
                  {
                    value: 'all',
                    label: t(
                      'admin.timecodeSync.filterSinceAll',
                    ),
                  },
                  {
                    value: '24',
                    label: t(
                      'admin.timecodeSync.filterSince24h',
                    ),
                  },
                  {
                    value: '168',
                    label: t(
                      'admin.timecodeSync.filterSince7d',
                    ),
                  },
                ]}
              />
            </div>
          </section>
          <section className="admin-card">
            <div className="admin-toolbar">
              <StatusPill kind="warn">
                {t('admin.timecodeSync.statQueued', {
                  count: data?.counts.queued ?? 0,
                })}
              </StatusPill>
              <StatusPill kind="ok">
                {t('admin.timecodeSync.statRunning', {
                  count: data?.counts.running ?? 0,
                })}
              </StatusPill>
              <span className="admin-card__sub">
                {t('admin.timecodeSync.statCandidates', {
                  count: data?.candidate_count ?? 0,
                })}
              </span>
            </div>
          </section>
          <section className="admin-card">
            <h2>{t('admin.timecodeSync.nowTitle')}</h2>
            <div
              style={{
                display: 'grid',
                gap: 12,
                gridTemplateColumns:
                  'repeat(auto-fit, minmax(240px, 1fr))',
              }}
            >
              {data?.running ? (
                <div>
                  <QueueJobCard
                    job={data.running}
                    badge={t(
                      'admin.timecodeSync.badgeRunning',
                    )}
                  />
                  <MotionPress
                    variant="ghost"
                    disabled={cancelMutation.isPending}
                    onClick={() =>
                      cancelMutation.mutate(
                        data.running!.id,
                      )
                    }
                  >
                    {t('admin.timecodeSync.cancelJob')}
                  </MotionPress>
                </div>
              ) : (
                <p className="admin-card__sub">
                  {t('admin.timecodeSync.noneRunning')}
                </p>
              )}
              {data?.next ? (
                <QueueJobCard
                  job={data.next}
                  badge={t('admin.timecodeSync.badgeNext')}
                />
              ) : (
                <p className="admin-card__sub">
                  {t('admin.timecodeSync.noneNext')}
                </p>
              )}
            </div>
          </section>
          <section className="admin-card">
            <h2>{t('admin.timecodeSync.queuedTitle')}</h2>
            <p className="admin-card__sub">
              {t('admin.timecodeSync.queuedHint')}
            </p>
            <DataTable
              columns={queuedColumns}
              rows={data?.queued ?? []}
              enableSorting={false}
              emptyHint={t(
                'admin.timecodeSync.queuedEmpty',
              )}
            />
          </section>
          <section className="admin-card">
            <h2>{t('admin.timecodeSync.recentTitle')}</h2>
            <DataTable
              columns={recentColumns}
              rows={data?.recent ?? []}
              enableSorting
              emptyHint={t(
                'admin.timecodeSync.recentEmpty',
              )}
            />
          </section>
        </>
      )}
    </div>
  )
}
