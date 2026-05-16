import { useEffect, useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type {
  ImportAudioInfo,
  ImportExternalTrackInfo,
  ImportJobResponse,
} from '@/types/api'
import { ImportSourcePicker } from './ImportSourcePicker'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  EXTERNAL_SOURCES,
  ACCOUNT_IMPORT_SOURCES,
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

import '@/styles/redesign-upload.css'

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
const PAGE_SIZE = 100

interface ImportViewProps {
  active: boolean
  onImportComplete?: (job: ImportJobData) => void
}

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

export function ImportView({
  active,
  onImportComplete,
}: ImportViewProps) {
  const { t } = useTranslation()
  const [phase, setPhase] = useState<Phase>('pick')
  const [job, setJob] = useState<ImportJobData | null>(null)
  const [audios, setAudios] = useState<AudioInfo[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [selectionMode, setSelectionMode] = useState<'all' | 'custom'>('all')
  const [totalTracks, setTotalTracks] = useState(0)
  const [loadedOffset, setLoadedOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const error = useRef<string | null>(null)
  const [errorState, setErrorState] = useState<string | null>(null)
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
  const [scanSlowHint, setScanSlowHint] = useState(false)
  const pollCountRef = useRef(0)
  const MAX_POLLS = 90
  const SCAN_SLOW_POLLS = 15

  const setError = useCallback((msg: string | null) => {
    error.current = msg
    setErrorState(msg)
  }, [])

  const isExternalSource = useCallback(
    (src: string) =>
      EXTERNAL_SOURCES.has(src) || ACCOUNT_IMPORT_SOURCES.has(src),
    [],
  )

  const normalizePageItem = useCallback(
    (t: ImportExternalTrackInfo, srcKey: string, idx: number): ImportAudioInfo => {
      const raw = t as unknown as Record<string, unknown>
      return {
        file_id: `${srcKey}:${idx}`,
        title: String(raw.title ?? ''),
        performer: (raw.artist ?? raw.performer ?? null) as string | null,
        duration: (raw.duration_seconds ?? raw.duration ?? null) as
          | number
          | null,
        file_size: (raw.file_size ?? null) as number | null,
      }
    },
    [],
  )

  const enterSelectPhaseFromJob = useCallback(
    async (j: ImportJobData) => {
      setJob(j)
      setScanningSource(undefined)

      if (isExternalSource(j.source)) {
        const page = await api.getImportTracks(j.id, 0, PAGE_SIZE)
        const tracks = page.items.map((t, i) =>
          normalizePageItem(t, j.source, i),
        )
        setAudios(tracks)
        setTotalTracks(page.total)
        setLoadedOffset(page.items.length)
        setHasMore(page.items.length < page.total)
        setSelectionMode('all')
        setSelected(new Set())
      } else {
        const list = normalizeJobTracks(j)
        setAudios(list)
        setTotalTracks(list.length)
        setLoadedOffset(list.length)
        setHasMore(false)
        const all = new Set<number>(
          list
            .map((_, i) => i)
            .filter(
              (i) =>
                !list[i].file_size || list[i].file_size! <= MAX_FILE_SIZE,
            ),
        )
        setSelectionMode('custom')
        setSelected(all)
      }
      setPhase('select')
    },
    [isExternalSource, normalizePageItem],
  )

  useEffect(() => {
    if (!active) return
    api.getActiveImport().then((j) => {
      if (j && j.status === 'importing') {
        setJob(j)
        setPhase('importing')
      } else if (j && j.status === 'queued') {
        setJob(j)
        setPhase('queued')
      } else if (j && j.status === 'scanning') {
        setJob(j)
        setScanningSource(j.source)
        setPhase('scanning')
      } else if (j && j.status === 'ready') {
        void enterSelectPhaseFromJob(j)
      }
    }).catch(() => {})
  }, [active, enterSelectPhaseFromJob])

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

  useEffect(() => {
    if (
      (phase !== 'importing' && phase !== 'queued' && phase !== 'scanning') ||
      !job
    )
      return
    pollCountRef.current = 0
    setScanSlowHint(false)
    const interval = setInterval(async () => {
      pollCountRef.current++
      if (
        phase === 'scanning' &&
        pollCountRef.current === SCAN_SLOW_POLLS
      ) {
        setScanSlowHint(true)
      }
      if (pollCountRef.current > MAX_POLLS) {
        clearInterval(interval)
        setError(t('import.jobTimeout'))
        setScanSlowHint(false)
        setPhase('pick')
        return
      }
      try {
        const updated = await api.getImportStatus(job.id)
        setJob(updated)

        if (phase === 'scanning') {
          if (updated.status === 'ready') {
            clearInterval(interval)
            setScanSlowHint(false)
            void enterSelectPhaseFromJob(updated)
          } else if (
            updated.status === 'failed' ||
            updated.status === 'cancelled'
          ) {
            clearInterval(interval)
            setScanSlowHint(false)
            setScanningSource(undefined)
            if (updated.status === 'cancelled') {
              setPhase('pick')
            } else {
              const code = updated.tracks_data?.error_code as
                | string
                | undefined
              const fallback = extScanError(code)
              setError(scanErrorMessage(fallback, updated))
              setPhase('pick')
            }
          }
          return
        }

        if (updated.status === 'done' || updated.status === 'cancelled') {
          if (updated.status === 'done') {
            onImportComplete?.(updated)
          }
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
  }, [phase, job?.id, onImportComplete, extScanError, enterSelectPhaseFromJob, t])

  const applyScanResult = useCallback(
    (j: ImportJobData): boolean => {
      if (j.status === 'failed') {
        setJob(j)
        setScanningSource(undefined)
        return false
      }
      void enterSelectPhaseFromJob(j)
      return true
    },
    [enterSelectPhaseFromJob],
  )

  const loadMoreTracks = useCallback(async () => {
    if (!job || !hasMore || loadingMore) return
    setLoadingMore(true)
    try {
      const page = await api.getImportTracks(job.id, loadedOffset, PAGE_SIZE)
      const baseIdx = loadedOffset
      const tracks = page.items.map((t, i) =>
        normalizePageItem(t, job.source, baseIdx + i),
      )
      setAudios((prev) => [...prev, ...tracks])
      setLoadedOffset((prev) => prev + page.items.length)
      setHasMore(baseIdx + page.items.length < page.total)
    } catch {
    } finally {
      setLoadingMore(false)
    }
  }, [job, hasMore, loadingMore, loadedOffset, normalizePageItem])

  useEffect(() => {
    if (phase !== 'select' || !hasMore) return
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void loadMoreTracks()
      },
      { rootMargin: '200px' },
    )
    obs.observe(sentinel)
    observerRef.current = obs
    return () => {
      obs.disconnect()
      observerRef.current = null
    }
  }, [phase, hasMore, loadMoreTracks])

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
      if (j.status === 'scanning') {
        setJob(j)
        setYandexModalOpen(false)
        return
      }
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
        if (j.status === 'scanning') {
          setJob(j)
          setVkModalOpen(false)
          return
        }
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
        if (j.status === 'scanning') {
          setJob(j)
          setScModalOpen(false)
          return
        }
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
        if (j.status === 'scanning') {
          setJob(j)
          setSpotifyModalOpen(false)
          return
        }
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
    if (selectionMode === 'all') {
      const next = new Set<number>()
      for (let i = 0; i < totalTracks; i++) {
        if (i !== idx) next.add(i)
      }
      setSelectionMode('custom')
      setSelected(next)
    } else {
      setSelected((prev) => {
        const next = new Set(prev)
        if (next.has(idx)) next.delete(idx)
        else next.add(idx)
        return next
      })
    }
  }

  const selectAll = () => {
    setSelectionMode('all')
    setSelected(new Set())
  }

  const deselectAll = () => {
    setSelectionMode('custom')
    setSelected(new Set())
  }

  const selectedCount =
    selectionMode === 'all' ? totalTracks : selected.size

  const isTrackSelected = (idx: number): boolean =>
    selectionMode === 'all' ? !selected.has(idx) : selected.has(idx)

  const handleStartImport = async () => {
    if (!job) return
    try {
      const indices =
        selectionMode === 'all'
          ? Array.from({ length: totalTracks }, (_, i) => i)
          : Array.from(selected)
      const updated = await api.startImportJob(job.id, indices)
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
    setSelectionMode('all')
    setTotalTracks(0)
    setLoadedOffset(0)
    setHasMore(false)
    setError(null)
    setScanningSource(undefined)
    setScanSlowHint(false)
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
      {errorState && (
        <div className="form-error" style={{ margin: '16px' }}>{errorState}</div>
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
          {scanSlowHint && (
            <p className="import-scan-slow-hint">
              {t('import.scanSlowHint')}
            </p>
          )}
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="btn-secondary import-scan-cancel-btn"
            disabled={cancelling}
            onClick={() => setCancelConfirmOpen(true)}
          >
            {cancelling ? t('import.cancelling') : t('playlists.cancel')}
          </MotionPress>
        </div>
      )}

      {phase === 'select' && (
        <div className="import-select">
          <div className="view-header">
            <h2>
              {t('import.foundCount', {
                count: totalTracks,
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
              const tooBig =
                audio.file_size != null && audio.file_size > MAX_FILE_SIZE
              const checked = isTrackSelected(i)
              return (
                <label
                  key={audio.file_id || i}
                  className={`import-track-item${tooBig ? ' disabled' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={tooBig}
                    onChange={() => toggleTrack(i)}
                  />
                  <div className="import-track-info">
                    <span className="import-track-title">
                      {audio.title}
                    </span>
                    <span className="import-track-meta">
                      {audio.performer || t('trackCard.unknownArtist')}
                      {audio.duration
                        ? ` · ${fmtDuration(audio.duration)}`
                        : ''}
                      {audio.file_size
                        ? ` · ${fmtSize(audio.file_size)}`
                        : ''}
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
            {hasMore && (
              <div
                ref={sentinelRef}
                className="import-load-sentinel"
                aria-hidden="true"
              >
                {loadingMore && (
                  <div
                    className="loader"
                    style={{ margin: '8px auto', width: 20, height: 20 }}
                  />
                )}
              </div>
            )}
          </div>

          <div className="rf-import-action-row">
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              disabled={selectedCount === 0}
              onClick={handleStartImport}
            >
              {t('import.importBtn', {
                count: selectedCount,
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
