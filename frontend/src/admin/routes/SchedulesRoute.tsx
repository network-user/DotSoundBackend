import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import {
  StatusPill,
  type StatusKind,
} from '../components/widgets/StatusPill'

interface ScheduleRow {
  id: string
  name: string
  task_name: string
  queue: string
  cron: string
  payload: Record<string, unknown> | null
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  last_status: string | null
  last_error: string | null
  last_job_id: string | null
}

function statusKindFor(s: string | null): StatusKind {
  if (!s) return 'unknown'
  if (s === 'queued') return 'ok'
  if (s === 'skipped_duplicate') return 'unknown'
  if (s === 'kick_failed' || s === 'invalid_cron')
    return 'error'
  if (s === 'task_missing') return 'error'
  return 'warn'
}

function cronHint(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return ''
  const [min, hour, dom, , dow] = parts
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const padT = (h: string, m: string) =>
    h === '*' || m === '*'
      ? ''
      : ` at ${h.padStart(2, '0')}:${m.padStart(2, '0')}`
  if (
    min.startsWith('*/') &&
    hour === '*' &&
    dom === '*' &&
    dow === '*'
  )
    return `Every ${min.slice(2)} min`
  if (
    min === '0' &&
    hour.startsWith('*/') &&
    dom === '*' &&
    dow === '*'
  )
    return `Every ${hour.slice(2)} h`
  if (dom === '*' && dow === '*')
    return `Daily${padT(hour, min)}`
  if (
    dom === '*' &&
    !dow.includes('/') &&
    !dow.includes(',')
  ) {
    const n = parseInt(dow)
    const name = Number.isNaN(n) ? dow : (days[n] ?? dow)
    return `Every ${name}${padT(hour, min)}`
  }
  if (dom !== '*' && !dom.includes('/') && dow === '*')
    return `Monthly on ${dom}th${padT(hour, min)}`
  return ''
}

function fmtTime(iso: string | null): string {
  if (!iso) return '–'
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString()
  } catch {
    return iso
  }
}

interface DraftSchedule {
  name: string
  task_name: string
  cron: string
  queue: string
  payload: string
  enabled: boolean
}

const EMPTY_DRAFT: DraftSchedule = {
  name: '',
  task_name: '',
  cron: '',
  queue: 'default',
  payload: '',
  enabled: true,
}

export function SchedulesRoute() {
  const { t } = useTranslation()
  const { showConfirm } = useAdminPrompt()
  const qc = useQueryClient()
  const [editing, setEditing] = useState<
    | { mode: 'create' }
    | { mode: 'edit'; id: string }
    | null
  >(null)
  const [draft, setDraft] = useState<DraftSchedule>(EMPTY_DRAFT)
  const [formError, setFormError] = useState<string | null>(
    null,
  )

  const schedules = useQuery({
    queryKey: ['admin', 'schedules'],
    queryFn: () => adminApi.listSchedules(),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })

  const invalidate = () =>
    qc.invalidateQueries({
      queryKey: ['admin', 'schedules'],
    })

  const runNow = useMutation({
    mutationFn: (id: string) => adminApi.runScheduleNow(id),
    onSuccess: () => {
      invalidate()
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.schedules.runDone'),
        durationMs: 2200,
      })
    },
    onError: () => {
      showIsland({
        kind: 'error',
        title: t('redesign.admin.schedules.runFailed'),
        durationMs: 4000,
      })
    },
  })

  const toggleEnabled = useMutation({
    mutationFn: (row: ScheduleRow) =>
      adminApi.updateSchedule(row.id, {
        enabled: !row.enabled,
      }),
    onSuccess: () => {
      invalidate()
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.schedules.toggleDone'),
        durationMs: 1800,
      })
    },
  })

  const removeSchedule = useMutation({
    mutationFn: (id: string) => adminApi.deleteSchedule(id),
    onSuccess: () => {
      invalidate()
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.schedules.deleteDone'),
        durationMs: 2200,
      })
    },
  })

  const saveSchedule = useMutation({
    mutationFn: async () => {
      let payload: Record<string, unknown> | null = null
      const trimmed = draft.payload.trim()
      if (trimmed) {
        try {
          payload = JSON.parse(trimmed)
        } catch (e) {
          throw new Error(
            t('admin.schedules.errors.payloadJson') as string,
          )
        }
      }
      if (editing?.mode === 'edit') {
        return adminApi.updateSchedule(editing.id, {
          task_name: draft.task_name || undefined,
          cron: draft.cron || undefined,
          queue: draft.queue || undefined,
          payload,
          enabled: draft.enabled,
        })
      }
      return adminApi.createSchedule({
        name: draft.name,
        task_name: draft.task_name,
        cron: draft.cron,
        queue: draft.queue || 'default',
        payload,
        enabled: draft.enabled,
      })
    },
    onSuccess: () => {
      setEditing(null)
      setDraft(EMPTY_DRAFT)
      setFormError(null)
      invalidate()
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.schedules.saveDone'),
        durationMs: 2400,
      })
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : String(err)
      setFormError(msg)
    },
  })

  const handleEdit = (row: ScheduleRow) => {
    setDraft({
      name: row.name,
      task_name: row.task_name,
      cron: row.cron,
      queue: row.queue,
      payload: row.payload
        ? JSON.stringify(row.payload, null, 2)
        : '',
      enabled: row.enabled,
    })
    setFormError(null)
    setEditing({ mode: 'edit', id: row.id })
  }

  const handleDelete = async (row: ScheduleRow) => {
    const ok = await showConfirm(
      t('admin.schedules.confirmDelete', {
        name: row.name,
      }),
      { danger: true },
    )
    if (!ok) return
    removeSchedule.mutate(row.id)
  }

  const columns: ColumnDef<ScheduleRow>[] = [
    {
      header: t('admin.schedules.cols.name') as string,
      accessorKey: 'name',
      cell: (i) => (
        <div className="admin-mono">
          {i.getValue<string>()}
        </div>
      ),
    },
    {
      header: t('admin.schedules.cols.task') as string,
      accessorKey: 'task_name',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<string>()}
        </span>
      ),
    },
    {
      header: t('admin.schedules.cols.cron') as string,
      accessorKey: 'cron',
      cell: (i) => {
        const expr = i.getValue<string>()
        const hint = cronHint(expr)
        return (
          <div>
            <span className="admin-mono">{expr}</span>
            {hint && (
              <div className="admin-cron-hint">{hint}</div>
            )}
          </div>
        )
      },
    },
    {
      header: t('admin.schedules.cols.queue') as string,
      accessorKey: 'queue',
    },
    {
      header: t('admin.schedules.cols.enabled') as string,
      accessorKey: 'enabled',
      cell: (i) => (
        <StatusPill
          kind={i.row.original.enabled ? 'ok' : 'unknown'}
        >
          {i.row.original.enabled
            ? (t('admin.schedules.enabledOn') as string)
            : (t('admin.schedules.enabledOff') as string)}
        </StatusPill>
      ),
    },
    {
      header: t('admin.schedules.cols.lastRun') as string,
      accessorFn: (row) => row.last_run_at,
      cell: (i) =>
        fmtTime(i.row.original.last_run_at),
    },
    {
      header: t('admin.schedules.cols.nextRun') as string,
      accessorFn: (row) => row.next_run_at,
      cell: (i) =>
        fmtTime(i.row.original.next_run_at),
    },
    {
      header: t('admin.schedules.cols.lastStatus') as string,
      accessorKey: 'last_status',
      cell: (i) => {
        const s = i.row.original.last_status
        if (!s) return '–'
        return (
          <StatusPill kind={statusKindFor(s)} title={
            i.row.original.last_error || undefined
          }>
            {s}
          </StatusPill>
        )
      },
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: (i) => {
        const row = i.row.original
        return (
          <div className="admin-toolbar admin-toolbar--compact">
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={() => runNow.mutate(row.id)}
              disabled={runNow.isPending}
            >
              {t('admin.schedules.actions.runNow')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={() => toggleEnabled.mutate(row)}
              disabled={toggleEnabled.isPending}
            >
              {row.enabled
                ? t('admin.schedules.actions.disable')
                : t('admin.schedules.actions.enable')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={() => handleEdit(row)}
            >
              {t('admin.schedules.actions.edit')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link admin-link--danger"
              onClick={() => handleDelete(row)}
            >
              {t('admin.schedules.actions.delete')}
            </MotionPress>
          </div>
        )
      },
    },
  ]

  const rows =
    (schedules.data?.items as ScheduleRow[] | undefined) ||
    []

  return (
    <div>
      <h1>{t('admin.schedules.title')}</h1>
      <section className="admin-card">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.schedules.list')}
          </h2>
          <MotionPress
            variant="primary"
            onClick={() => {
              setDraft(EMPTY_DRAFT)
              setFormError(null)
              setEditing({ mode: 'create' })
            }}
          >
            {t('admin.schedules.actions.create')}
          </MotionPress>
        </div>
        <p className="admin-card__sub">
          {t('admin.schedules.hint')}
        </p>
        {schedules.isError && (
          <p className="admin-error" role="alert">
            {t('admin.schedules.loadFailed')}
          </p>
        )}
        <DataTable
          columns={columns}
          rows={rows}
          enableSorting
          emptyHint={t('admin.schedules.empty') as string}
        />
      </section>

      {editing && (
        <section className="admin-card">
          <h2>
            {editing.mode === 'edit'
              ? t('admin.schedules.editTitle')
              : t('admin.schedules.createTitle')}
          </h2>
          <div className="admin-form-grid">
            <label className="admin-field">
              <span>{t('admin.schedules.fields.name')}</span>
              <input
                type="text"
                value={draft.name}
                disabled={editing.mode === 'edit'}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    name: e.target.value,
                  }))
                }
                placeholder="weekly_playlist_refresh"
              />
            </label>
            <label className="admin-field">
              <span>{t('admin.schedules.fields.task')}</span>
              <input
                type="text"
                value={draft.task_name}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    task_name: e.target.value,
                  }))
                }
                placeholder="admin.alert.send"
              />
            </label>
            <label className="admin-field">
              <span>{t('admin.schedules.fields.cron')}</span>
              <input
                type="text"
                value={draft.cron}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    cron: e.target.value,
                  }))
                }
                placeholder="0 4 * * 1"
              />
              {draft.cron && cronHint(draft.cron) && (
                <span className="admin-cron-hint">
                  {cronHint(draft.cron)}
                </span>
              )}
            </label>
            <label className="admin-field">
              <span>
                {t('admin.schedules.fields.queue')}
              </span>
              <input
                type="text"
                value={draft.queue}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    queue: e.target.value,
                  }))
                }
                placeholder="default"
              />
            </label>
            <label className="admin-field admin-field--wide">
              <span>
                {t('admin.schedules.fields.payload')}
              </span>
              <textarea
                value={draft.payload}
                rows={6}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    payload: e.target.value,
                  }))
                }
                placeholder='{"key":"value"}'
              />
            </label>
            <label className="admin-field admin-field--inline">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    enabled: e.target.checked,
                  }))
                }
              />
              <span>
                {t('admin.schedules.fields.enabled')}
              </span>
            </label>
          </div>
          {formError && (
            <p className="admin-error" role="alert">
              {formError}
            </p>
          )}
          <div className="admin-toolbar">
            <MotionPress
              variant="primary"
              onClick={() => saveSchedule.mutate()}
              disabled={saveSchedule.isPending}
            >
              {t('admin.schedules.actions.save')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={() => {
                setEditing(null)
                setFormError(null)
              }}
            >
              {t('admin.schedules.actions.cancel')}
            </MotionPress>
          </div>
        </section>
      )}
    </div>
  )
}
