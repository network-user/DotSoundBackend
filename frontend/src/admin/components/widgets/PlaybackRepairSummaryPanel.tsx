import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  StatusPill,
  type StatusKind,
} from './StatusPill'

export interface PlaybackRepairSummaryItem {
  job_id: string
  track_id: number | null
  status: string
  progress_id: string | null
  stage: string | null
  updated_at: string | null
}

export interface PlaybackRepairDiagnosticItem {
  job_id: string
  track_id: number | null
  status: string
  outcome: string
  detail: string | null
  http_status: number | null
  source_platform: string | null
  sc_url_before: string | null
  sc_url_after: string | null
  candidate_found: boolean | null
  candidate_url: string | null
  candidate_title: string | null
  rejected_reason: string | null
  conflict_track_id: number | null
  refresh_error: string | null
}

export interface PlaybackRepairSummary {
  requested: number
  matched: number
  processed: number
  remaining: number
  statuses: Record<string, number>
  outcomes: Record<string, number>
  stages: Record<string, number>
  current: PlaybackRepairSummaryItem | null
  items: PlaybackRepairSummaryItem[]
  unresolved_items?: PlaybackRepairDiagnosticItem[]
  retryable_track_ids?: number[]
}

interface Props {
  summary: PlaybackRepairSummary
  title?: string
  onOpenTasks?: () => void
  onOpenTrack?: (trackId: number) => void
  onRetryUnresolved?: (jobIds: string[]) => void
  retryingUnresolved?: boolean
  onClose?: () => void
}

const STAGE_PREFIX = 'admin.tasks.bg.playbackRepair.stages.'

function count(
  source: Record<string, number> | undefined,
  key: string,
): number {
  return source?.[key] ?? 0
}

function percent(summary: PlaybackRepairSummary): number {
  const total = summary.matched || summary.requested || 0
  if (total <= 0) return 0
  return Math.min(
    100,
    Math.round((summary.processed / total) * 100),
  )
}

function statusKind(status: string | null | undefined): StatusKind {
  if (status === 'done' || status === 'repaired') return 'ok'
  if (
    status === 'failed' ||
    status === 'failed_terminal' ||
    status === 'error' ||
    status === 'unresolved'
  ) {
    return 'error'
  }
  if (
    status === 'queued' ||
    status === 'running' ||
    status === 'cancelling'
  ) {
    return 'warn'
  }
  return 'unknown'
}

function shortUrl(url: string | null | undefined): string {
  if (!url) return '—'
  return url.replace(/^https?:\/\//, '')
}

function repairReasonLabel(
  t: TFunction,
  reason: string | null | undefined,
): string {
  if (!reason) return String(t('admin.tasks.bg.playbackRepair.reasonUnknown'))
  const key = `admin.tasks.bg.playbackRepair.reasons.${reason}`
  const label = String(t(key))
  return label === key ? reason : label
}

export function playbackRepairStageLabel(
  t: TFunction,
  stage: string | null | undefined,
): string {
  if (!stage) {
    return String(t('admin.tasks.bg.playbackRepair.stages.unknown'))
  }
  const key = `${STAGE_PREFIX}${stage}`
  const label = String(t(key))
  return label === key ? stage : label
}

export function PlaybackRepairSummaryPanel({
  summary,
  title,
  onOpenTasks,
  onOpenTrack,
  onRetryUnresolved,
  retryingUnresolved = false,
  onClose,
}: Props) {
  const { t } = useTranslation()
  const total = summary.matched || summary.requested
  const current = summary.current
  const currentStage = current?.stage ?? (
    summary.remaining === 0 ? 'repaired' : 'queued'
  )
  const width = `${percent(summary)}%`
  const unresolvedItems = summary.unresolved_items || []
  const retryJobIds = unresolvedItems.map((item) => item.job_id)
  const outcomeItems = [
    ['repaired', count(summary.outcomes, 'repaired')],
    ['unresolved', count(summary.outcomes, 'unresolved')],
    ['skipped', count(summary.outcomes, 'skipped')],
    ['not_found', count(summary.outcomes, 'not_found')],
    ['error', count(summary.outcomes, 'error')],
    ['cancelled', count(summary.outcomes, 'cancelled')],
  ] as const

  return (
    <div className="admin-playback-repair-summary">
      <div className="admin-playback-repair-summary__head">
        <div className="admin-playback-repair-summary__title">
          <strong>
            {title ?? t('admin.tasks.bg.playbackRepair.title')}
          </strong>
          <span>
            {t('admin.tasks.bg.playbackRepair.progress', {
              processed: summary.processed,
              total,
            })}
          </span>
        </div>
        <div className="admin-toolbar admin-toolbar--compact">
          {onOpenTasks && (
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={onOpenTasks}
            >
              {t('admin.tasks.bg.playbackRepair.openTasks')}
            </MotionPress>
          )}
          {onRetryUnresolved && retryJobIds.length > 0 && (
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              disabled={retryingUnresolved}
              onClick={() => onRetryUnresolved(retryJobIds)}
            >
              {retryingUnresolved
                ? t('admin.tasks.bg.playbackRepair.retrying')
                : t('admin.tasks.bg.playbackRepair.retryUnresolved', {
                    count: retryJobIds.length,
                  })}
            </MotionPress>
          )}
          {onClose && (
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={onClose}
            >
              {t('admin.tasks.bg.playbackRepair.close')}
            </MotionPress>
          )}
        </div>
      </div>
      <div className="admin-playback-repair-summary__bar">
        <div style={{ width }} />
      </div>
      <div className="admin-playback-repair-summary__stats">
        <div>
          <span>{t('admin.tasks.bg.playbackRepair.current')}</span>
          <StatusPill kind={statusKind(current?.status ?? currentStage)}>
            {playbackRepairStageLabel(t, currentStage)}
          </StatusPill>
        </div>
        <div>
          <span>{t('admin.tasks.bg.playbackRepair.queued')}</span>
          <strong>{count(summary.statuses, 'queued')}</strong>
        </div>
        <div>
          <span>{t('admin.tasks.bg.playbackRepair.running')}</span>
          <strong>{count(summary.statuses, 'running')}</strong>
        </div>
        <div>
          <span>{t('admin.tasks.bg.playbackRepair.remaining')}</span>
          <strong>{summary.remaining}</strong>
        </div>
      </div>
      <div className="admin-playback-repair-summary__outcomes">
        {outcomeItems.map(([key, value]) => (
          <span key={key}>
            {t(`admin.tasks.bg.playbackRepair.outcomes.${key}`)}:{' '}
            <strong>{value}</strong>
          </span>
        ))}
      </div>
      {current && (
        <div className="admin-playback-repair-summary__current">
          <span className="admin-mono">{current.job_id.slice(0, 12)}</span>
          {current.track_id != null && (
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={() => onOpenTrack?.(current.track_id as number)}
            >
              {t('admin.tasks.bg.playbackRepair.openTrack', {
                id: current.track_id,
              })}
            </MotionPress>
          )}
        </div>
      )}
      {unresolvedItems.length > 0 && (
        <div className="admin-playback-repair-summary__diagnostics">
          <div className="admin-playback-repair-summary__diag-head">
            <strong>
              {t('admin.tasks.bg.playbackRepair.unresolvedTitle')}
            </strong>
            <span>
              {t('admin.tasks.bg.playbackRepair.unresolvedHint')}
            </span>
          </div>
          <div className="admin-playback-repair-summary__diag-table">
            <table>
              <thead>
                <tr>
                  <th>{t('admin.tasks.bg.playbackRepair.diagTrack')}</th>
                  <th>{t('admin.tasks.bg.playbackRepair.diagSource')}</th>
                  <th>{t('admin.tasks.bg.playbackRepair.diagReason')}</th>
                  <th>{t('admin.tasks.bg.playbackRepair.diagCandidate')}</th>
                  <th>{t('admin.tasks.bg.playbackRepair.diagDetail')}</th>
                </tr>
              </thead>
              <tbody>
                {unresolvedItems.map((item) => (
                  <tr key={item.job_id}>
                    <td>
                      {item.track_id != null ? (
                        <MotionPress
                          variant="ghost"
                          haptic="selection"
                          className="admin-link admin-mono"
                          onClick={() => onOpenTrack?.(item.track_id as number)}
                        >
                          #{item.track_id}
                        </MotionPress>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                    <td>
                      <span className="admin-mono">
                        {shortUrl(item.sc_url_before || item.sc_url_after)}
                      </span>
                    </td>
                    <td>
                      <StatusPill kind="error">
                        {repairReasonLabel(t, item.rejected_reason)}
                      </StatusPill>
                    </td>
                    <td>
                      <span className="admin-mono">
                        {item.candidate_found === false
                          ? t('admin.tasks.bg.playbackRepair.noCandidate')
                          : shortUrl(item.candidate_url)}
                      </span>
                    </td>
                    <td>
                      <span>
                        {item.refresh_error ||
                          item.detail ||
                          t('admin.tasks.bg.playbackRepair.noDetail')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
