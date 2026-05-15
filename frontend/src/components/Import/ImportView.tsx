import { useEffect, useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type { ImportAudioInfo, ImportJobResponse } from '@/types/api'
import { ImportSourcePicker } from './ImportSourcePicker'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  fmtDuration,
  fmtSize,
  normalizeJobTracks,
  scanningLabel,
} from './importJobUtils'
import { SoundCloudPlaylistUrlModal } from './SoundCloudPlaylistUrlModal'
import { SpotifyUrlModal } from './SpotifyUrlModal'
import { VkMusicUrlModal } from './VkMusicUrlModal'
import { YandexMusicUrlModal } from './YandexMusicUrlModal'
import { PlatformImportMethodModal } from './PlatformImportMethodModal'

type AudioInfo = ImportAudioInfo
type ImportJobData = ImportJobResponse

type Phase =
  | 'pick'
  | 'scanning'
  | 'select'
  | 'queued'
  | 'importing'
  | 'done'

const MAX_FILE_SIZE = 20 * 1024 * 1024

function scanErrorMessage(
  fallback: string,
  job: ImportJobData,
): string {
  const code = job.tracks_data?.error_code?.trim()
  const message = job.tracks_data?.error_message?.trim()
  const detail = [
    code ? `code=${code}` : '',
    message && message !== code ? message : '',
  ].filter(Boolean).join('; ')
  return detail ? `${fallback} (${detail})` : fallback
}

export function ImportView({ active }: { active: boolean }) {
  const { t } = useTranslation()
  const [phase, setPhase] = useState<Phase>('pick')
  const [job, setJob] = useState<ImportJobData | null>(null)
  const [audios, setAudios] = useState<AudioInfo[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [scanningSource, setScanningSource] = useState<string | undefined>()
  const [yandexModalOpen, setYandexModalOpen] = useState(false)
  const [vkModalOpen, setVkModalOpen] = useState(false)
  const [scModalOpen, setScModalOpen] = useState(false)
  const [spotifyModalOpen, setSpotifyModalOpen] = useState(false)
  const [importMethodPlatform, setImportMethodPlatform] = useState<
    null | 'vk' | 'spotify'
  >(null)
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const pollCountRef = useRef(0)
  const MAX_POLLS = 150

  useEffect(() => {
    if (!active) return
    api.getActiveImport().then((j) => {
      if (j && j.status === 'importing') {
        setJob(j)
        setPhase('importing')
      } else if (j && j.status === 'queued') {
        setJob(j)
        setPhase('queued')
      } else if (j && j.status === 'ready') {
        setJob(j)
        const list = normalizeJobTracks(j)
        setAudios(list)
        const all = new Set<number>(
          list
            .map((_, i) => i)
            .filter((i) => {
              const a = list[i]
              return !a.file_size || a.file_size <= MAX_FILE_SIZE
            })
        )
        setSelected(all)
        setPhase('select')
      }
    }).catch(() => {})
  }, [active])

  useEffect(() => {
    if ((phase !== 'importing' && phase !== 'queued') || !job)
      return
    pollCountRef.current = 0
    const interval = setInterval(async () => {
      pollCountRef.current++
      if (pollCountRef.current > MAX_POLLS) {
        clearInterval(interval)
        setError(t('import.jobTimeout'))
        setPhase('pick')
        return
      }
      try {
        const updated = await api.getImportStatus(job.id)
        setJob(updated)
        if (updated.status === 'done' || updated.status === 'cancelled') {
          setPhase('done')
          clearInterval(interval)
        } else if (updated.status === 'importing' && phase === 'queued') {
          setPhase('importing')
        } else if (updated.status === 'queued' && phase === 'importing') {
          setPhase('queued')
        }
      } catch {}
    }, 2000)
    return () => clearInterval(interval)
  }, [phase, job?.id, t])

  const applyScanResult = useCallback((j: ImportJobData): boolean => {
    setJob(j)
    setScanningSource(undefined)
    if (j.status === 'failed') {
      return false
    }
    const list = normalizeJobTracks(j)
    setAudios(list)
    const all = new Set<number>(
      list
        .map((_, i) => i)
        .filter(
          i => !list[i].file_size || list[i].file_size! <= MAX_FILE_SIZE,
        ),
    )
    setSelected(all)
    setPhase('select')
    return true
  }, [])

  const extScanError = useCallback(
    (code: string | undefined) => {
      if (code === 'not_found') {
        return t('import.listNotFound')
      }
      if (code === 'private') {
        return t('import.listPrivate')
      }
      if (code === 'invalid_url') {
        return t('import.listBadUrl')
      }
      return t('import.listGeneric')
    },
    [t],
  )

  const handleSourceSelect = useCallback(async (sourceId: string) => {
    setError(null)
    if (sourceId === 'yandex') {
      setYandexModalOpen(true)
      return
    }
    if (sourceId === 'vk') {
      setImportMethodPlatform('vk')
      return
    }
    if (sourceId === 'soundcloud') {
      setScModalOpen(true)
      return
    }
    if (sourceId === 'spotify') {
      setImportMethodPlatform('spotify')
      return
    }
    if (sourceId !== 'telegram') return
    setPhase('scanning')
    setScanningSource('telegram')
    try {
      const j = await api.startTelegramImport()
      if (!applyScanResult(j)) {
        setError(scanErrorMessage(t('import.profileTracksFail'), j))
        setPhase('pick')
        setScanningSource(undefined)
      }
    } catch {
      setError(t('import.botError'))
      setPhase('pick')
      setScanningSource(undefined)
    }
  }, [applyScanResult, t])

  const handleYandexScan = useCallback(async (url: string) => {
    setError(null)
    setPhase('scanning')
    setScanningSource('yandex_music')
    try {
      const j = await api.startYandexMusicImport(url)
      if (j.status === 'failed') {
        const code = j.tracks_data?.error_code
        const msg =
          code === 'not_found'
            ? t('import.yandexScanNotFound')
            : code === 'private'
              ? t('import.yandexScanPrivate')
              : code === 'invalid_url'
                ? t('import.yandexScanBadUrl')
                : t('import.yandexScanGeneric')
        setPhase('pick')
        setScanningSource(undefined)
        throw new Error(scanErrorMessage(msg, j))
      }
      applyScanResult(j)
      setYandexModalOpen(false)
    } catch (e) {
      setPhase('pick')
      setScanningSource(undefined)
      throw e
    }
  }, [applyScanResult, t])

  const handleVkScan = useCallback(
    async (url: string) => {
      setError(null)
      setPhase('scanning')
      setScanningSource('vk_music')
      try {
        const j = await api.startVkMusicImport(url)
        if (j.status === 'failed') {
          const code = j.tracks_data?.error_code
          const msg =
            code === 'not_found'
              ? t('import.vkNotFound')
              : code === 'private'
                ? t('import.vkPrivate')
                : code === 'invalid_url'
                  ? t('import.vkBadUrl')
                  : t('import.vkGeneric')
          setPhase('pick')
          setScanningSource(undefined)
          throw new Error(scanErrorMessage(msg, j))
        }
        applyScanResult(j)
        setVkModalOpen(false)
      } catch (e) {
        setPhase('pick')
        setScanningSource(undefined)
        throw e
      }
    },
    [applyScanResult, t],
  )

  const handleSoundCloudScan = useCallback(
    async (url: string) => {
      setError(null)
      setPhase('scanning')
      setScanningSource('soundcloud_playlist')
      try {
        const j = await api.startSoundCloudPlaylistImport(url)
        if (j.status === 'failed') {
          const code = j.tracks_data?.error_code as string | undefined
          setPhase('pick')
          setScanningSource(undefined)
          throw new Error(scanErrorMessage(extScanError(code), j))
        }
        applyScanResult(j)
        setScModalOpen(false)
      } catch (e) {
        setPhase('pick')
        setScanningSource(undefined)
        throw e
      }
    },
    [applyScanResult, extScanError, t],
  )

  const handleSpotifyScan = useCallback(
    async (url: string) => {
      setError(null)
      setPhase('scanning')
      setScanningSource('spotify')
      try {
        const j = await api.startSpotifyImport(url)
        if (j.status === 'failed') {
          const code = j.tracks_data?.error_code as string | undefined
          setPhase('pick')
          setScanningSource(undefined)
          throw new Error(scanErrorMessage(extScanError(code), j))
        }
        applyScanResult(j)
        setSpotifyModalOpen(false)
      } catch (e) {
        setPhase('pick')
        setScanningSource(undefined)
        throw e
      }
    },
    [applyScanResult, extScanError, t],
  )

  const applyAccountImportJob = useCallback(
    (j: ImportJobData) => {
      setError(null)
      if (j.status === 'failed') {
        const code = j.tracks_data?.error_code as string | undefined
        setPhase('pick')
        setScanningSource(undefined)
        setError(
          scanErrorMessage(extScanError(code), j) ||
            t('import.accountTracks'),
        )
        return
      }
      if (!applyScanResult(j)) {
        setError(t('import.accountTracksShort'))
        setPhase('pick')
        setScanningSource(undefined)
      }
    },
    [applyScanResult, extScanError, t],
  )

  const toggleTrack = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const selectAll = () => {
    const all = new Set<number>(
      audios.map((_, i) => i)
        .filter((i) => !audios[i].file_size || audios[i].file_size! <= MAX_FILE_SIZE)
    )
    setSelected(all)
  }

  const deselectAll = () => setSelected(new Set())

  const handleStartImport = async () => {
    if (!job) return
    try {
      const updated = await api.startImportJob(job.id, Array.from(selected))
      setJob(updated)
      setPhase(updated.status === 'queued' ? 'queued' : 'importing')
    } catch {
      setError(t('import.importStartFail'))
    }
  }

  const handleReset = () => {
    setPhase('pick')
    setJob(null)
    setAudios([])
    setSelected(new Set())
    setError(null)
    setScanningSource(undefined)
    pollCountRef.current = 0
  }

  const handleCancelConfirm = async () => {
    if (!job || cancelling) return
    setCancelling(true)
    try {
      await api.cancelImport(job.id)
      setCancelConfirmOpen(false)
      handleReset()
    } catch {
      setError(t('import.importCancelFail'))
      setCancelConfirmOpen(false)
    } finally {
      setCancelling(false)
    }
  }

  if (!active) return null

  return (
    <div className="import-view">
      {error && (
        <div className="form-error" style={{ margin: '16px' }}>{error}</div>
      )}

      {phase === 'pick' && (
        <ImportSourcePicker onSelect={handleSourceSelect} />
      )}

      {phase === 'scanning' && (
        <div className="import-scanning">
          <div className="loader" />
          <p className="empty-hint">
            {scanningLabel(job?.source ?? scanningSource)}
          </p>
        </div>
      )}

      {phase === 'select' && (
        <div className="import-select">
          <div className="view-header">
            <h2>
              {t('import.foundCount', {
                count: audios.length,
              })}
            </h2>
            <span className="hint">
              {t('import.selectHint')}
            </span>
          </div>

          <div className="import-select-actions">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary"
              onClick={selectAll}
            >
              {t('import.selectAll')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary"
              onClick={deselectAll}
            >
              {t('import.deselectAll')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary rf-import-cancel-action"
              onClick={() => setCancelConfirmOpen(true)}
            >
              {t('playlists.cancel')}
            </MotionPress>
          </div>

          <div className="import-track-list">
            {audios.map((audio, i) => {
              const tooBig = audio.file_size != null && audio.file_size > MAX_FILE_SIZE
              return (
                <label
                  key={audio.file_id || i}
                  className={`import-track-item${tooBig ? ' disabled' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(i)}
                    disabled={tooBig}
                    onChange={() => toggleTrack(i)}
                  />
                  <div className="import-track-info">
                    <span className="import-track-title">{audio.title}</span>
                    <span className="import-track-meta">
                      {audio.performer || t('trackCard.unknownArtist')}
                      {audio.duration ? ` · ${fmtDuration(audio.duration)}` : ''}
                      {audio.file_size ? ` · ${fmtSize(audio.file_size)}` : ''}
                    </span>
                    {tooBig && (
                      <span className="import-track-warning">
                        {t('import.fileTooBig')}
                      </span>
                    )}
                  </div>
                </label>
              )
            })}
          </div>

          <div className="rf-import-action-row">
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              disabled={selected.size === 0}
              onClick={handleStartImport}
            >
              {t('import.importBtn', {
                count: selected.size,
              })}
            </MotionPress>
          </div>
        </div>
      )}

      {phase === 'queued' && job && (
        <div className="import-queued">
          <div className="view-header">
            <h2>{t('import.queueTitle')}</h2>
            <span className="hint">
              {job.queue_position
                ? t('import.queuePos', {
                  pos: job.queue_position,
                })
                : t('import.queueWait')}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              margin: '0 16px',
            }}
          >
            <div
              className="loader"
              aria-hidden="true"
              style={{ margin: 0, flexShrink: 0 }}
            />
            <p
              className="empty-hint"
              style={{ margin: 0 }}
            >
              {t('import.queueMsg')}
            </p>
          </div>
          <div className="rf-import-action-row">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary rf-import-action-full"
              onClick={() => setCancelConfirmOpen(true)}
              disabled={cancelling}
            >
              {t('playlists.cancel')}
            </MotionPress>
          </div>
        </div>
      )}

      {phase === 'importing' && job && (
        <div className="import-progress">
          <div className="view-header">
            <h2>{t('import.importing')}</h2>
            <span className="hint">
              {job.completed_tracks + job.failed_tracks} / {job.total_tracks}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              margin: '0 16px',
            }}
          >
            <div
              className="loader"
              aria-hidden="true"
              style={{ margin: 0, flexShrink: 0 }}
            />
            <div
              className="progress-bar-wrap"
              style={{ flex: 1 }}
            >
              <div
                className="progress-bar-fill"
                style={{
                  width: job.total_tracks
                    ? `${((job.completed_tracks + job.failed_tracks) / job.total_tracks) * 100}%`
                    : '0%',
                }}
              />
            </div>
          </div>
          <p className="progress-label">
            {t('import.progressLine', {
              done: job.completed_tracks,
              failed: job.failed_tracks,
            })}
          </p>
          <p className="empty-hint">
            {t('import.importBackground')}
          </p>
          <div className="rf-import-action-row rf-import-action-row--bottom">
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary rf-import-action-full"
              onClick={() => setCancelConfirmOpen(true)}
              disabled={cancelling}
            >
              {t('import.cancelImport')}
            </MotionPress>
          </div>
        </div>
      )}

      {phase === 'done' && job && (
        <div className="import-done">
          <div className="view-header">
            <h2>{t('import.doneTitle')}</h2>
            <span className="hint">
              {t('import.doneStats', {
                done: job.completed_tracks,
                total: job.total_tracks,
              })}
              {job.failed_tracks > 0
                ? t('import.doneFailed', {
                  n: job.failed_tracks,
                })
                : ''}
            </span>
          </div>
          <p
            className="empty-hint"
            style={{ margin: '0 16px 12px' }}
          >
            {t('import.doneBody')}
          </p>
          <div className="rf-import-action-row rf-import-action-row--bottom-clean">
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              onClick={handleReset}
            >
              {t('import.importMore')}
            </MotionPress>
          </div>
        </div>
      )}

      <YandexMusicUrlModal
        open={yandexModalOpen}
        onClose={() => setYandexModalOpen(false)}
        onScan={handleYandexScan}
      />

      <VkMusicUrlModal
        open={vkModalOpen}
        onClose={() => setVkModalOpen(false)}
        onScan={handleVkScan}
      />

      <SoundCloudPlaylistUrlModal
        open={scModalOpen}
        onClose={() => setScModalOpen(false)}
        onScan={handleSoundCloudScan}
      />

      <SpotifyUrlModal
        open={spotifyModalOpen}
        onClose={() => setSpotifyModalOpen(false)}
        onScan={handleSpotifyScan}
      />

      <PlatformImportMethodModal
        open={importMethodPlatform != null}
        platform={importMethodPlatform === 'vk' ? 'vk' : 'spotify'}
        onClose={() => setImportMethodPlatform(null)}
        onPickByLink={() => {
          const p = importMethodPlatform
          setImportMethodPlatform(null)
          if (p === 'vk') setVkModalOpen(true)
          else if (p === 'spotify') setSpotifyModalOpen(true)
        }}
        onAccountScanReady={j => {
          setImportMethodPlatform(null)
          setScanningSource(j.source)
          applyAccountImportJob(j)
        }}
      />

      {cancelConfirmOpen && (
        <div
          className="modal"
          onClick={(e) => {
            if (e.target === e.currentTarget && !cancelling) {
              setCancelConfirmOpen(false)
            }
          }}
        >
          <div className="modal-content">
            <div className="modal-header">
              <h3>{t('import.cancelDialogTitle')}</h3>
            </div>
            <p className="modal-hint">
              {t('import.cancelDialogBody')}
            </p>
            <div className="rf-import-confirm-row">
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="btn-secondary rf-import-confirm-btn"
                onClick={() => setCancelConfirmOpen(false)}
                disabled={cancelling}
              >
                {t('import.continueImport')}
              </MotionPress>
              <MotionPress
                type="button"
                variant="primary"
                haptic="medium"
                className="btn-primary rf-import-confirm-btn"
                onClick={handleCancelConfirm}
                disabled={cancelling}
              >
                {cancelling
                  ? t('import.cancelling')
                  : t('import.confirmCancel')}
              </MotionPress>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
