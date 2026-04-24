import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { SoundCloudPlaylistUrlModal } from '@/components/Import/SoundCloudPlaylistUrlModal'
import { SpotifyUrlModal } from '@/components/Import/SpotifyUrlModal'
import { VkMusicUrlModal } from '@/components/Import/VkMusicUrlModal'
import { YandexMusicUrlModal } from '@/components/Import/YandexMusicUrlModal'
import { PlatformImportMethodModal } from '@/components/Import/PlatformImportMethodModal'
import {
  defaultSelectedIndices,
  fmtDuration,
  fmtSize,
  MAX_FILE_SIZE,
  normalizeJobTracks,
  scanningLabel,
} from '@/components/Import/importJobUtils'
import type { ImportAudioInfo, ImportJobResponse, OnboardingStatus } from '@/types/api'

type Flow =
  | 'pick'
  | 'scanning'
  | 'select'
  | 'queued'
  | 'importing'
  | 'done'
  | 'empty'

interface Props {
  onDone: () => void
}

const MAX_POLLS = 150
const POLL_MS = 2000

export function OnboardingImportStep({ onDone }: Props) {
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [yandexOpen, setYandexOpen] = useState(false)
  const [vkOpen, setVkOpen] = useState(false)
  const [scOpen, setScOpen] = useState(false)
  const [spotifyOpen, setSpotifyOpen] = useState(false)
  const [importMethod, setImportMethod] = useState<
    null | 'vk' | 'spotify'
  >(null)
  const [flow, setFlow] = useState<Flow>('pick')
  const [job, setJob] = useState<ImportJobResponse | null>(null)
  const [audios, setAudios] = useState<ImportAudioInfo[]>([])
  const [selected, setSelected] = useState<Set<number>>(() => new Set())
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(
    false,
  )
  const [cancelling, setCancelling] = useState(false)
  const pollCountRef = useRef(0)

  useEffect(() => {
    api
      .getOnboardingStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    if (flow !== 'queued' && flow !== 'importing')
      return
    if (!job) return
    pollCountRef.current = 0
    const t = window.setInterval(async () => {
      pollCountRef.current++
      if (pollCountRef.current > MAX_POLLS) {
        window.clearInterval(t)
        setErr('Импорт занял слишком много времени. Попробуйте в профиле.')
        setFlow('pick')
        setJob(null)
        setAudios([])
        setSelected(new Set())
        return
      }
      try {
        const updated = await api.getImportStatus(job.id)
        setJob(updated)
        if (updated.status === 'done' || updated.status === 'cancelled') {
          window.clearInterval(t)
          if (updated.status === 'done') {
            setFlow('done')
          } else {
            setFlow('pick')
            setJob(null)
            setAudios([])
            setSelected(new Set())
          }
        } else if (updated.status === 'importing') {
          setFlow('importing')
        } else if (updated.status === 'queued') {
          setFlow('queued')
        }
      } catch {
        /* next poll */
      }
    }, POLL_MS)
    return () => window.clearInterval(t)
  }, [flow, job?.id])

  const applyScanJob = useCallback(
    (j: ImportJobResponse) => {
      if (j.status === 'failed') {
        return false
      }
      setJob(j)
      const list = normalizeJobTracks(j)
      if (list.length === 0) {
        setFlow('empty')
        return true
      }
      setAudios(list)
      setSelected(defaultSelectedIndices(list))
      setFlow('select')
      return true
    },
    [],
  )

  const backToSources = useCallback(async () => {
    setErr(null)
    if (job && (flow === 'select' || flow === 'empty')) {
      setBusy(true)
      try {
        await api.cancelImport(job.id)
      } catch {
        /* best-effort; всё равно уйдём с шага */
      } finally {
        setBusy(false)
      }
    }
    setJob(null)
    setAudios([])
    setSelected(new Set())
    setFlow('pick')
  }, [job, flow])

  const onTelegram = async () => {
    setErr(null)
    setFlow('scanning')
    setJob(null)
    setBusy(true)
    try {
      const j = await api.startTelegramImport()
      if (!applyScanJob(j)) {
        setErr('Не удалось прочитать музыку из Telegram')
        setFlow('pick')
      }
    } catch {
      setErr('Не удалось связаться с ботом')
      setFlow('pick')
    } finally {
      setBusy(false)
    }
  }

  const onYandexUrl = async (url: string) => {
    setErr(null)
    setBusy(true)
    try {
      const j = await api.startYandexMusicImport(url)
      if (j.status === 'failed') {
        throw new Error('scan_failed')
      }
      setYandexOpen(false)
      if (!applyScanJob(j)) {
        setErr('Не удалось прочитать плейлист')
        setFlow('pick')
      }
    } catch {
      setErr('Не удалось прочитать плейлист')
      setFlow('pick')
    } finally {
      setBusy(false)
    }
  }

  const onVkUrl = async (url: string) => {
    setErr(null)
    setBusy(true)
    try {
      const j = await api.startVkMusicImport(url)
      if (j.status === 'failed') {
        throw new Error('scan_failed')
      }
      setVkOpen(false)
      if (!applyScanJob(j)) {
        setErr('Не удалось прочитать плейлист')
        setFlow('pick')
      }
    } catch {
      setErr('Не удалось прочитать плейлист')
      setFlow('pick')
    } finally {
      setBusy(false)
    }
  }

  const onSoundCloudUrl = async (url: string) => {
    setErr(null)
    setBusy(true)
    try {
      const j = await api.startSoundCloudPlaylistImport(url)
      if (j.status === 'failed') {
        throw new Error('scan_failed')
      }
      setScOpen(false)
      if (!applyScanJob(j)) {
        setErr('Не удалось прочитать плейлист')
        setFlow('pick')
      }
    } catch {
      setErr('Не удалось прочитать плейлист')
      setFlow('pick')
    } finally {
      setBusy(false)
    }
  }

  const onSpotifyUrl = async (url: string) => {
    setErr(null)
    setBusy(true)
    try {
      const j = await api.startSpotifyImport(url)
      if (j.status === 'failed') {
        throw new Error('scan_failed')
      }
      setSpotifyOpen(false)
      if (!applyScanJob(j)) {
        setErr('Не удалось прочитать плейлист')
        setFlow('pick')
      }
    } catch {
      setErr('Не удалось прочитать плейлист')
      setFlow('pick')
    } finally {
      setBusy(false)
    }
  }

  const toggleTrack = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) {
        next.delete(idx)
      } else {
        next.add(idx)
      }
      return next
    })
  }

  const selectAll = () => {
    setSelected(
      new Set(
        audios
          .map((_, i) => i)
          .filter(
            (i) =>
              !audios[i].file_size ||
              audios[i].file_size! <= MAX_FILE_SIZE,
          ),
      ),
    )
  }

  const deselectAll = () => {
    setSelected(new Set())
  }

  const handleStartImport = async () => {
    if (!job) return
    setErr(null)
    setBusy(true)
    try {
      const updated = await api.startImportJob(
        job.id,
        Array.from(selected),
      )
      setJob(updated)
      setFlow(
        updated.status === 'queued' ? 'queued' : 'importing',
      )
    } catch {
      setErr('Не удалось запустить импорт')
    } finally {
      setBusy(false)
    }
  }

  const continueAfterImport = async () => {
    setErr(null)
    setBusy(true)
    try {
      await api.acknowledgeOnboardingImport()
      onDone()
    } catch {
      setErr('Не удалось сохранить')
    }
    setBusy(false)
  }

  const finish = async () => {
    setBusy(true)
    try {
      await api.acknowledgeOnboardingImport()
      onDone()
    } catch {
      setErr('Не удалось сохранить')
    }
    setBusy(false)
  }

  const handleCancelConfirm = async () => {
    if (!job || cancelling) {
      return
    }
    setCancelling(true)
    try {
      await api.cancelImport(job.id)
      setCancelConfirmOpen(false)
      setJob(null)
      setAudios([])
      setSelected(new Set())
      setFlow('pick')
    } catch {
      setErr('Не удалось отменить импорт')
      setCancelConfirmOpen(false)
    } finally {
      setCancelling(false)
    }
  }

  if (!status) {
    return (
      <div className="onboarding-step">
        <div className="onboarding-import-skeleton">
          <div className="loader" />
          <p className="onboarding-subtitle">Проверяем профиль…</p>
        </div>
      </div>
    )
  }

  const showTg = status.can_import_from_telegram

  if (flow === 'empty') {
    return (
      <div className="onboarding-step">
        <h2 className="onboarding-title">Ничего не найдено</h2>
        <p className="onboarding-subtitle">
          Треков для переноса в этом сценарии сейчас
          нет. Можно вернуться к другому источнику или
          сразу перейти к жанрам.
        </p>
        {err && (
          <p className="form-error" style={{ marginTop: 12 }}>
            {err}
          </p>
        )}
        <div className="onboarding-import-footer-btns">
          <button
            type="button"
            className="onboarding-skip"
            onClick={backToSources}
            disabled={busy}
          >
            К источникам
          </button>
          <button
            type="button"
            className="onboarding-next"
            onClick={continueAfterImport}
            disabled={busy}
          >
            {busy ? '…' : 'Продолжить к жанрам'}
          </button>
        </div>
      </div>
    )
  }

  if (flow === 'done' && job) {
    return (
      <div className="onboarding-step">
        <h2 className="onboarding-title">Импорт готов</h2>
        <p className="onboarding-subtitle">
          В медиатеке: {job.completed_tracks} из{' '}
          {job.total_tracks} тр.
          {job.failed_tracks > 0 &&
            ` · не удалось: ${job.failed_tracks}`}
        </p>
        <p
          className="onboarding-subtitle"
          style={{ fontSize: 14, color: 'var(--text-muted)' }}
        >
          Можно продолжать настройку: жанры и далее
          по плану.
        </p>
        {err && (
          <p className="form-error" style={{ marginTop: 12 }}>
            {err}
          </p>
        )}
        <div className="onboarding-import-footer-btns" style={{ marginTop: 20 }}>
          <button
            type="button"
            className="onboarding-next"
            style={{ maxWidth: '100%', width: '100%' }}
            onClick={continueAfterImport}
            disabled={busy}
          >
            {busy ? '…' : 'Продолжить к жанрам'}
          </button>
        </div>
      </div>
    )
  }

  if (flow === 'select' && job) {
    return (
      <div className="onboarding-step">
        {err && (
          <p className="form-error" style={{ marginBottom: 12 }}>
            {err}
          </p>
        )}
        <div className="import-select">
          <h2 className="onboarding-title" style={{ marginBottom: 8 }}>
            К импорту: {audios.length}
          </h2>
          <p
            className="onboarding-subtitle"
            style={{ marginBottom: 16, textAlign: 'left' }}
          >
            Снимите галочки с треков, если не
            &nbsp;нужны, затем
            <strong> Импорт</strong> — в фон.
          </p>

          <div className="import-select-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={selectAll}
            >
              Все
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={deselectAll}
            >
              Снять
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setCancelConfirmOpen(true)}
              style={{ marginLeft: 'auto' }}
            >
              Отмена
            </button>
          </div>

          <div className="import-track-list">
            {audios.map((audio, i) => {
              const tooBig =
                audio.file_size != null &&
                audio.file_size > MAX_FILE_SIZE
              return (
                <label
                  key={audio.file_id || i}
                  className={
                    'import-track-item' +
                    (tooBig ? ' disabled' : '')
                  }
                >
                  <input
                    type="checkbox"
                    checked={selected.has(i)}
                    disabled={tooBig}
                    onChange={() => toggleTrack(i)}
                  />
                  <div className="import-track-info">
                    <span className="import-track-title">
                      {audio.title}
                    </span>
                    <span className="import-track-meta">
                      {audio.performer || 'Неизвестный'}
                      {audio.duration
                        ? ` · ${fmtDuration(
                            audio.duration,
                          )}`
                        : ''}
                      {audio.file_size
                        ? ` · ${fmtSize(audio.file_size)}`
                        : ''}
                    </span>
                    {tooBig && (
                      <span className="import-track-warning">
                        Файл &gt; 20 МБ
                      </span>
                    )}
                  </div>
                </label>
              )
            })}
          </div>

          <div style={{ padding: '8px 0 0' }}>
            <button
              type="button"
              className="onboarding-next"
              style={{ width: '100%' }}
              disabled={selected.size === 0 || busy}
              onClick={handleStartImport}
            >
              {busy
                ? '…'
                : `Импорт (${selected.size})`}
            </button>
          </div>
        </div>
        {cancelConfirmOpen && (
          <div
            className="modal"
            onClick={e => {
              if (e.target === e.currentTarget && !cancelling) {
                setCancelConfirmOpen(false)
              }
            }}
          >
            <div className="modal-content">
              <div className="modal-header">
                <h3>Остановить?</h3>
              </div>
              <p className="modal-hint">
                Импорт не
                &nbsp;запущен — вернётесь к
                &nbsp;выбору
                &nbsp;источника
                {'.'}
              </p>
              <div
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}
              >
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setCancelConfirmOpen(false)}
                  disabled={cancelling}
                  style={{ flex: 1 }}
                >
                  Нет
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={backToSources}
                  disabled={cancelling}
                  style={{ flex: 1 }}
                >
                  К источникам
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  if (
    (flow === 'queued' || flow === 'importing') &&
    job
  ) {
    return (
      <div className="onboarding-step">
        {err && (
          <p className="form-error" style={{ marginBottom: 12 }}>
            {err}
          </p>
        )}
        {flow === 'queued' && (
          <div className="import-queued">
            <h2 className="onboarding-title">В очереди</h2>
            <p
              className="onboarding-subtitle"
              style={{ textAlign: 'left' }}
            >
              {job.queue_position
                ? `Позиция: ${job.queue_position}`
                : 'Ждём свободный слот...'}
            </p>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                margin: '8px 0 16px',
              }}
            >
              <div className="loader" style={{ margin: 0 }} />
            </div>
            <button
              type="button"
              className="btn-secondary"
              style={{ width: '100%' }}
              onClick={() => setCancelConfirmOpen(true)}
            >
              Отменить
            </button>
            <button
              type="button"
              className="onboarding-skip"
              style={{
                width: '100%',
                marginTop: 8,
                border: 0,
              }}
              onClick={continueAfterImport}
              disabled={busy}
            >
              К жанрам, импорт пойдёт в фоне
            </button>
          </div>
        )}
        {flow === 'importing' && (
          <div className="import-progress">
            <h2 className="onboarding-title">Идёт импорт</h2>
            <p
              className="onboarding-subtitle"
              style={{ textAlign: 'left' }}
            >
              {job.completed_tracks + job.failed_tracks} /{' '}
              {job.total_tracks} · ош.: {job.failed_tracks}
            </p>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                margin: '8px 0 12px',
              }}
            >
              <div className="loader" style={{ margin: 0 }} />
              <div
                className="progress-bar-wrap"
                style={{ flex: 1 }}
              >
                <div
                  className="progress-bar-fill"
                  style={{
                    width: job.total_tracks
                      ? `${(
                          (job.completed_tracks +
                            job.failed_tracks) /
                          job.total_tracks) *
                        100
                        }%`
                      : '0%',
                  }}
                />
              </div>
            </div>
            <p
              className="onboarding-subtitle"
              style={{
                fontSize: 12,
                color: 'var(--text-muted)',
              }}
            >
              Можно подождать здесь или
              &nbsp;продолжать настройку: импорт
              &nbsp;дойдёт
              &nbsp;в
              &nbsp;фоне, прогресс
              &nbsp;— в
              &nbsp;панели
              {'. '}
            </p>
            <button
              type="button"
              className="btn-secondary"
              style={{ width: '100%', marginTop: 8 }}
              onClick={() => setCancelConfirmOpen(true)}
            >
              Отменить импорт
            </button>
            <button
              type="button"
              className="onboarding-skip"
              style={{
                width: '100%',
                marginTop: 8,
                border: 0,
              }}
              onClick={continueAfterImport}
              disabled={busy}
            >
              К жанрам, импорт пойдёт в фоне
            </button>
          </div>
        )}
        {cancelConfirmOpen && (
          <div
            className="modal"
            onClick={e => {
              if (e.target === e.currentTarget && !cancelling) {
                setCancelConfirmOpen(false)
              }
            }}
          >
            <div className="modal-content">
              <div className="modal-header">
                <h3>Отменить импорт?</h3>
              </div>
              <p className="modal-hint">
                Можно вернуться к
                &nbsp;источникам;
                &nbsp;текущий
                &nbsp;запуск
                &nbsp;будет
                &nbsp;сброшен
                {'. '}
              </p>
              <div
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}
              >
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setCancelConfirmOpen(false)}
                  disabled={cancelling}
                  style={{ flex: 1 }}
                >
                  Продолжить
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleCancelConfirm}
                  disabled={cancelling}
                  style={{ flex: 1 }}
                >
                  {cancelling ? '…' : 'Отменить'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  if (flow === 'scanning') {
    return (
      <div className="onboarding-step">
        <div className="import-scanning">
          <div className="loader" />
          <p className="empty-hint" style={{ marginTop: 16 }}>
            {scanningLabel(job?.source)}
          </p>
        </div>
        <YandexMusicUrlModal
          open={yandexOpen}
          onClose={() => setYandexOpen(false)}
          onScan={onYandexUrl}
        />
        <VkMusicUrlModal
          open={vkOpen}
          onClose={() => setVkOpen(false)}
          onScan={onVkUrl}
        />
        <SpotifyUrlModal
          open={spotifyOpen}
          onClose={() => setSpotifyOpen(false)}
          onScan={onSpotifyUrl}
        />
        <SoundCloudPlaylistUrlModal
          open={scOpen}
          onClose={() => setScOpen(false)}
          onScan={onSoundCloudUrl}
        />
      </div>
    )
  }

  return (
    <div className="onboarding-step">
      <h2 className="onboarding-title">Перенесите свою музыку</h2>
      <p className="onboarding-subtitle">
        Можно импортировать в один заход, без
        лишних переходов, или
        &nbsp;пройти
        &nbsp;позже
        {'. '}
      </p>
      {err && (
        <p className="form-error" style={{ marginBottom: 12 }}>
          {err}
        </p>
      )}

      <div className="onboarding-import-cards">
        {showTg && (
          <button
            type="button"
            className="onboarding-import-card"
            onClick={onTelegram}
            disabled={busy}
          >
            <span className="onboarding-import-card-icon">
              <Icon name="source-telegram" size={24} />
            </span>
            <span className="onboarding-import-card-title">Telegram</span>
            <span className="hint">Аудио из вашего профиля</span>
          </button>
        )}

        <button
          type="button"
          className="onboarding-import-card"
          onClick={() => setYandexOpen(true)}
          disabled={busy}
        >
          <span className="onboarding-import-card-icon">
            <Icon name="source-yandex" size={24} />
          </span>
          <span className="onboarding-import-card-title">
            Яндекс.Музыка
          </span>
          <span className="hint">Ссылка на плейлист или альбом</span>
        </button>

        <button
          type="button"
          className="onboarding-import-card"
          onClick={() => setImportMethod('vk')}
          disabled={busy}
        >
          <span className="onboarding-import-card-icon">
            <Icon name="source-vk" size={24} />
          </span>
          <span className="onboarding-import-card-title">VK Музыка</span>
          <span className="hint">Ссылка или вход в аккаунт</span>
        </button>

        <button
          type="button"
          className="onboarding-import-card"
          onClick={() => setImportMethod('spotify')}
          disabled={busy}
        >
          <span className="onboarding-import-card-icon">
            <Icon name="source-spotify" size={24} />
          </span>
          <span className="onboarding-import-card-title">Spotify</span>
          <span className="hint">Ссылка или вход в аккаунт</span>
        </button>

        <button
          type="button"
          className="onboarding-import-card"
          onClick={() => setScOpen(true)}
          disabled={busy}
        >
          <span className="onboarding-import-card-icon">
            <Icon name="source-soundcloud" size={24} />
          </span>
          <span className="onboarding-import-card-title">SoundCloud</span>
          <span className="hint">Публичный плейлист (/sets/)</span>
        </button>
      </div>

      <div className="onboarding-import-footer-btns">
        <button
          type="button"
          className="onboarding-skip"
          onClick={finish}
          disabled={busy}
        >
          Позже
        </button>
        <button
          type="button"
          className="onboarding-next"
          onClick={finish}
          disabled={busy}
        >
          {busy ? '…' : 'Далее к жанрам'}
        </button>
      </div>

      <YandexMusicUrlModal
        open={yandexOpen}
        onClose={() => setYandexOpen(false)}
        onScan={onYandexUrl}
      />
      <VkMusicUrlModal
        open={vkOpen}
        onClose={() => setVkOpen(false)}
        onScan={onVkUrl}
      />
      <SpotifyUrlModal
        open={spotifyOpen}
        onClose={() => setSpotifyOpen(false)}
        onScan={onSpotifyUrl}
      />
      <PlatformImportMethodModal
        open={importMethod != null}
        platform={importMethod === 'vk' ? 'vk' : 'spotify'}
        onClose={() => setImportMethod(null)}
        onPickByLink={() => {
          const p = importMethod
          setImportMethod(null)
          if (p === 'vk') setVkOpen(true)
          else if (p === 'spotify') setSpotifyOpen(true)
        }}
        onAccountScanReady={j => {
          setImportMethod(null)
          setErr(null)
          if (j.status === 'failed') {
            setErr('Не удалось прочитать библиотеку. Попробуйте по ссылке.')
            return
          }
          if (!applyScanJob(j)) {
            setErr('Не удалось прочитать плейлист')
            setFlow('pick')
          }
        }}
      />
      <SoundCloudPlaylistUrlModal
        open={scOpen}
        onClose={() => setScOpen(false)}
        onScan={onSoundCloudUrl}
      />
    </div>
  )
}
