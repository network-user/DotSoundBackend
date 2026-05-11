import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence } from 'framer-motion'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { api, getApiErrorMessage } from '@/lib/api'
import { dismissIsland, showIsland } from '@/lib/island'
import { getInternalUserId } from '@/lib/telegram'
import { hapticNotification, hapticSelection } from '@/lib/telegram'
import type { LyricsResponse, Track } from '@/types/api'
import {
  coverBlobToFile,
  extractAudioMetadata,
  type AudioMetadata,
} from '@/lib/audioMetadata'
import {
  clearDraft,
  saveDraft,
  type UploadDraft,
} from '@/lib/uploadDraft'
import { LyricsEditor } from '../TrackCardSheet/LyricsEditor'
import { UploadStepAudio } from './steps/UploadStepAudio'
import { UploadStepDetails } from './steps/UploadStepDetails'
import { UploadStepCover } from './steps/UploadStepCover'
import { UploadStepPreview } from './steps/UploadStepPreview'
import { UploadProgressView } from './UploadProgressView'
import { DuplicateModal } from './DuplicateModal'
import { flagUploadV2 } from '@/lib/flags'
import { computeAudioHash } from '@/lib/audioHash'
import {
  checkDuplicate,
  initUpload,
  uploadFile,
} from '@/lib/chunkedUploader'

interface AutoFilledFlags {
  title?: boolean
  artist?: boolean
  genre?: boolean
  cover?: boolean
}

interface Props {
  onSuccess: (track: Track) => void
  initialDraft?: UploadDraft | null
}

const WIZARD_HINTS = [
  ['wizardAudioTitle', 'wizardAudioHint'],
  ['wizardDetailsTitle', 'wizardDetailsHint'],
  ['wizardCoverTitle', 'wizardCoverHint'],
  ['wizardPreviewTitle', 'wizardPreviewHint'],
] as const

const SEARCH_DEBOUNCE_MS = 220

export function UploadFileTab({ onSuccess, initialDraft }: Props) {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const transition = reduce ? TWEEN_FAST : SPRING_GENTLE

  const [title, setTitle] = useState(initialDraft?.title ?? '')
  const [artist, setArtist] = useState(initialDraft?.artistName ?? '')
  const [artistMode, setArtistMode] = useState<'profile' | 'custom'>(
    initialDraft?.artistMode ?? 'custom',
  )
  const [profileArtistName, setProfileArtistName] = useState<string | null>(
    null,
  )
  const [artistQuery, setArtistQuery] = useState(
    initialDraft?.artistQuery ?? '',
  )
  const [artistOpen, setArtistOpen] = useState(false)
  const [artistSearching, setArtistSearching] = useState(false)
  const [artistResults, setArtistResults] = useState<string[]>([])

  const [genre, setGenre] = useState(initialDraft?.genre ?? '')
  const [genreQuery, setGenreQuery] = useState(initialDraft?.genreQuery ?? '')
  const [genreOpen, setGenreOpen] = useState(false)
  const [genreSearching, setGenreSearching] = useState(false)
  const [genreResults, setGenreResults] = useState<string[]>([])
  const [genres, setGenres] = useState<string[]>([])

  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioDuration, setAudioDuration] = useState<number | null>(null)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(initialDraft?.isPublic ?? true)
  const [termsAccepted, setTermsAccepted] = useState(
    initialDraft?.termsAccepted ?? false,
  )
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const [lyrics, setLyrics] = useState<LyricsResponse | null>(
    initialDraft?.lyricsPlainText
      ? {
          track_id: 0,
          plain_text: initialDraft.lyricsPlainText,
          synced_lines: initialDraft.lyricsSyncedLines ?? null,
          source: 'manual',
          created_at: '',
          updated_at: '',
        }
      : null,
  )
  const [showLyricsEditor, setShowLyricsEditor] = useState(false)
  const [localAudioUrl, setLocalAudioUrl] = useState<string | null>(null)
  const [coverDragging, setCoverDragging] = useState(false)
  const [audioDragging, setAudioDragging] = useState(false)
  const [wizardStep, setWizardStep] = useState(0)
  const [autoFilled, setAutoFilled] = useState<AutoFilledFlags>({})
  const [autoDetecting, setAutoDetecting] = useState(false)
  const [uploadedTrackId, setUploadedTrackId] = useState<number | null>(null)
  const [audioHash, setAudioHash] = useState<string | null>(null)
  const [dupeMatch, setDupeMatch] = useState<{
    trackId: number
    title: string | null
    uploadedAt: string | null
  } | null>(null)
  const [allowDupe, setAllowDupe] = useState(false)

  useEffect(() => {
    api.getGenres().then(setGenres).catch(() => {})
  }, [])

  useEffect(() => {
    const userId = getInternalUserId()
    if (!userId) return
    api
      .getUserProfile(userId)
      .then((user) => {
        const display = user.display_name?.trim() ?? ''
        if (!display) {
          setProfileArtistName(null)
          setArtistMode('custom')
          return
        }
        setProfileArtistName(display)
        setArtist(display)
        setArtistQuery(display)
        setArtistMode('profile')
      })
      .catch(() => {})
  }, [])

  const normalizedGenres = useMemo(
    () => new Map(genres.map((g) => [g.toLowerCase(), g])),
    [genres],
  )

  useEffect(() => {
    const query = genreQuery.trim()
    if (!genreOpen || !query) {
      setGenreResults([])
      setGenreSearching(false)
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      setGenreSearching(true)
      void (async () => {
        const byName = genres
          .filter((g) =>
            g.toLowerCase().includes(query.toLowerCase()),
          )
          .slice(0, 8)
        const searchHits = await api
          .getTracks({ q: query, size: 30 })
          .catch(() => ({ items: [] as Track[] }))
        const genresFromEs = searchHits.items
          .map((tr) => tr.genre?.trim() ?? '')
          .filter((x) => x.length > 0)
        const merged = [...byName, ...genresFromEs]
        const seen = new Set<string>()
        const result: string[] = []
        for (const item of merged) {
          const key = item.toLowerCase()
          if (seen.has(key)) continue
          seen.add(key)
          result.push(normalizedGenres.get(key) ?? item)
          if (result.length >= 10) break
        }
        const exact = normalizedGenres.get(query.toLowerCase())
        if (
          exact &&
          !result.some(
            (value) => value.toLowerCase() === exact.toLowerCase(),
          )
        ) {
          result.unshift(exact)
        }
        if (!cancelled) {
          setGenreResults(result)
          setGenreSearching(false)
        }
      })()
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [genreOpen, genreQuery, genres, normalizedGenres])

  const hasExactGenre = useMemo(
    () => normalizedGenres.has(genreQuery.trim().toLowerCase()),
    [genreQuery, normalizedGenres],
  )

  useEffect(() => {
    const query = artistQuery.trim()
    if (!artistOpen || !query) {
      setArtistResults([])
      setArtistSearching(false)
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      setArtistSearching(true)
      void (async () => {
        const artistsFromApi = await api
          .getArtists(query, 12)
          .catch(() => ({ items: [] as { name: string }[] }))
        const trackHits = await api
          .getTracks({ q: query, size: 30 })
          .catch(() => ({ items: [] as Track[] }))
        const merged = [
          ...artistsFromApi.items.map((x) => x.name.trim()),
          ...trackHits.items
            .map((tr) => tr.artist?.trim() ?? '')
            .filter((x) => x.length > 0),
        ]
        const seen = new Set<string>()
        const result: string[] = []
        for (const item of merged) {
          const key = item.toLowerCase()
          if (seen.has(key)) continue
          seen.add(key)
          result.push(item)
          if (result.length >= 10) break
        }
        if (!cancelled) {
          setArtistResults(result)
          setArtistSearching(false)
        }
      })()
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [artistOpen, artistQuery])

  const hasExactArtist = useMemo(
    () =>
      artistResults.some(
        (value) => value.toLowerCase() === artistQuery.trim().toLowerCase(),
      ),
    [artistResults, artistQuery],
  )

  useEffect(() => {
    return () => {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
    }
  }, [localAudioUrl])

  useEffect(() => {
    if (uploading) return
    const timer = window.setTimeout(() => {
      saveDraft({
        stepIndex: wizardStep,
        title,
        artistMode,
        artistName: artist,
        artistQuery,
        genre,
        genreQuery,
        isPublic,
        termsAccepted,
        lyricsPlainText: lyrics?.plain_text ?? '',
        lyricsSyncedLines: lyrics?.synced_lines ?? null,
      })
    }, 500)
    return () => window.clearTimeout(timer)
  }, [
    title,
    artist,
    artistMode,
    artistQuery,
    genre,
    genreQuery,
    isPublic,
    termsAccepted,
    lyrics,
    wizardStep,
    uploading,
  ])

  const applyAudioFile = (file: File) => {
    setError('')
    setAudioFile(file)
    hapticSelection()
    if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
    const url = URL.createObjectURL(file)
    setLocalAudioUrl(url)

    const tmp = new Audio()
    tmp.preload = 'metadata'
    tmp.src = url
    tmp.onloadedmetadata = () => {
      setAudioDuration(tmp.duration)
    }

    setAutoDetecting(true)
    void extractAudioMetadata(file)
      .then((meta) => applyAutoFilled(meta, file.name))
      .catch(() => {})
      .finally(() => setAutoDetecting(false))

    setAudioHash(null)
    setDupeMatch(null)
    setAllowDupe(false)
    if (flagUploadV2()) {
      void (async () => {
        try {
          const hash = await computeAudioHash(file)
          setAudioHash(hash)
          const res = await checkDuplicate(hash, file.size)
          if (res.exists && res.track_id) {
            setDupeMatch({
              trackId: res.track_id,
              title: res.title ?? null,
              uploadedAt: res.uploaded_at ?? null,
            })
          }
        } catch {
          /* hash/dedupe is best-effort — never block the user */
        }
      })()
    }
  }

  function applyAutoFilled(meta: AudioMetadata, fileName: string): void {
    const next: AutoFilledFlags = {}
    if (meta.title && !title.trim()) {
      setTitle(meta.title)
      next.title = true
    }
    if (
      meta.artist &&
      artistMode === 'custom' &&
      !artist.trim() &&
      !artistQuery.trim()
    ) {
      setArtist(meta.artist)
      setArtistQuery(meta.artist)
      next.artist = true
    }
    if (meta.genre && !genre.trim() && !genreQuery.trim()) {
      const normalized =
        normalizedGenres.get(meta.genre.toLowerCase()) ?? meta.genre
      setGenre(normalized)
      setGenreQuery(normalized)
      next.genre = true
    }
    if (meta.cover && !coverFile) {
      void coverBlobToFile(
        meta.cover,
        sanitizeFileStem(fileName),
      ).then((file) => {
        setCoverFile(file)
        const reader = new FileReader()
        reader.onload = (ev) =>
          setCoverPreview(ev.target?.result as string)
        reader.readAsDataURL(file)
        setAutoFilled((prev) => ({ ...prev, cover: true }))
      })
    }
    if (Object.keys(next).length) {
      setAutoFilled((prev) => ({ ...prev, ...next }))
    }
  }

  function sanitizeFileStem(fileName: string): string {
    const stem = fileName.replace(/\.[a-z0-9]+$/i, '')
    return stem.replace(/[^\w.-]+/g, '_').slice(0, 64) || 'cover'
  }

  const applyCoverFile = (file: File) => {
    if (!file.type.startsWith('image/')) return
    setCoverFile(file)
    hapticSelection()
    const reader = new FileReader()
    reader.onload = (ev) =>
      setCoverPreview(ev.target?.result as string)
    reader.readAsDataURL(file)
    clearAutoFlag('cover')
  }

  const clearCover = () => {
    setCoverFile(null)
    setCoverPreview(null)
    clearAutoFlag('cover')
  }

  const clearAutoFlag = (field: keyof AutoFilledFlags) => {
    setAutoFilled((prev) => {
      if (!prev[field]) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }

  const reset = () => {
    setTitle('')
    setArtist('')
    setArtistMode(profileArtistName ? 'profile' : 'custom')
    setArtistQuery('')
    setArtistOpen(false)
    setArtistSearching(false)
    setArtistResults([])
    setGenre('')
    setGenreQuery('')
    setGenreOpen(false)
    setGenreSearching(false)
    setGenreResults([])
    setAudioFile(null)
    setAudioDuration(null)
    setCoverFile(null)
    setCoverPreview(null)
    setLyrics(null)
    setLocalAudioUrl(null)
    setError('')
    setUploading(false)
    setUploadDone(false)
    setIsPublic(true)
    setTermsAccepted(false)
    setWizardStep(0)
    setAutoFilled({})
    setAutoDetecting(false)
  }

  function syncGenreArtistDraft() {
    if (genreQuery.trim()) {
      const exact = normalizedGenres.get(
        genreQuery.trim().toLowerCase(),
      )
      setGenre(exact ?? genreQuery.trim())
    }
    if (artistMode === 'custom' && artistQuery.trim()) {
      setArtist(artistQuery.trim())
    }
    if (
      artistMode === 'profile' &&
      profileArtistName?.trim()
    ) {
      setArtist(profileArtistName.trim())
    }
  }

  function handleWizardNext() {
    setError('')
    if (wizardStep === 0) {
      if (!audioFile) {
        setError(t('redesign.upload.file.errorAudioRequired'))
        return
      }
      setWizardStep(1)
      return
    }
    if (wizardStep === 1) {
      syncGenreArtistDraft()
      if (!title.trim()) {
        setError(t('redesign.upload.file.errorTitleRequired'))
        return
      }
      if (
        artistMode === 'profile' &&
        !profileArtistName?.trim()
      ) {
        setError(t('redesign.upload.file.errorArtistProfile'))
        return
      }
      setWizardStep(2)
      return
    }
    if (wizardStep === 2) {
      setWizardStep(3)
    }
  }

  function handleWizardBack() {
    if (!uploading && wizardStep > 0) {
      setWizardStep((s) => Math.max(0, s - 1))
    }
  }

  function resolveSubmitError(err: unknown): string {
    const msg = err instanceof Error ? err.message : ''
    const fallback = t('redesign.upload.file.errorByCode.def')
    if (/^[1-5]\d{2}$/.test(msg)) {
      return t(`redesign.upload.file.errorByCode.${msg}`, {
        defaultValue: fallback,
      })
    }
    return getApiErrorMessage(err, fallback)
  }

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    setError('')
    syncGenreArtistDraft()
    if (artistMode === 'profile') {
      if (!profileArtistName?.trim()) {
        setError(t('redesign.upload.file.errorArtistProfile'))
        return
      }
      setArtist(profileArtistName.trim())
    }
    if (!title.trim()) {
      setError(t('redesign.upload.file.errorTitleRequired'))
      return
    }
    if (!audioFile) {
      setError(t('redesign.upload.file.errorAudioRequired'))
      return
    }
    if (!termsAccepted) {
      setError(t('redesign.upload.file.errorTermsRequired'))
      return
    }

    if (dupeMatch && !allowDupe) {
      // user must resolve the duplicate prompt first
      return
    }

    setUploading(true)
    setUploadDone(false)

    let islandId: string | undefined
    try {
      islandId = showIsland({
        kind: 'progress',
        title: t('redesign.upload.progressTitle'),
        hint: t('redesign.upload.progressHint'),
      })

      let uploaded: { id: number }

      if (flagUploadV2()) {
        const plan = await initUpload({
          filename: audioFile.name,
          mime: audioFile.type || 'audio/mpeg',
          total_size: audioFile.size,
          audio_hash: audioHash,
          title: title.trim(),
          artist: artist.trim() || null,
          use_profile_artist: artistMode === 'profile',
          genre: genre.trim() || null,
          is_public: isPublic,
          upload_terms_accepted: true,
        })
        const result = await uploadFile(plan, audioFile, {
          cover: coverFile,
        })
        uploaded = { id: result.track_id }
      } else {
        const fd = new FormData()
        fd.append('file', audioFile)
        fd.append('title', title.trim())
        if (artist.trim()) fd.append('artist', artist.trim())
        fd.append(
          'use_profile_artist',
          artistMode === 'profile' ? 'true' : 'false',
        )
        if (genre.trim()) fd.append('genre', genre.trim())
        if (coverFile) fd.append('cover', coverFile)
        fd.append('is_public', String(isPublic))
        fd.append('upload_terms_accepted', 'true')
        uploaded = await api.uploadTrack(fd)
      }

      if (lyrics) {
        if (lyrics.synced_lines) {
          await api.saveLyricsSync(uploaded.id, lyrics.synced_lines)
        } else {
          await api.saveLyrics(uploaded.id, lyrics.plain_text)
        }
      }
      setUploadDone(true)
      if (islandId) dismissIsland(islandId)
      showIsland({
        kind: 'toast',
        title: t('redesign.upload.doneToast'),
        durationMs: 2200,
      })
      hapticNotification('success')

      clearDraft()
      setUploadedTrackId(uploaded.id)
    } catch (err) {
      if (islandId) dismissIsland(islandId)
      setUploading(false)
      setUploadDone(false)
      setError(resolveSubmitError(err))
      hapticNotification('error')
    }
  }

  const draftArtistLabel =
    artistMode === 'profile'
      ? profileArtistName?.trim() || artist.trim()
      : artist.trim()

  if (uploadedTrackId !== null) {
    return (
      <UploadProgressView
        trackId={uploadedTrackId}
        onOpenTrack={async () => {
          const fullTrack = await api.getTrack(uploadedTrackId)
          setUploadedTrackId(null)
          reset()
          onSuccess(fullTrack)
        }}
        onUploadAnother={() => {
          setUploadedTrackId(null)
          reset()
        }}
      />
    )
  }

  const dupeModal =
    dupeMatch && audioFile ? (
      <DuplicateModal
        filename={audioFile.name}
        existingTitle={dupeMatch.title}
        existingTrackId={dupeMatch.trackId}
        uploadedAt={dupeMatch.uploadedAt}
        onOpen={async (id) => {
          try {
            const full = await api.getTrack(id)
            setDupeMatch(null)
            reset()
            onSuccess(full)
          } catch {
            setDupeMatch(null)
          }
        }}
        onUploadAnyway={() => {
          setAllowDupe(true)
          setDupeMatch(null)
        }}
        onCancel={() => {
          setDupeMatch(null)
          setAudioFile(null)
          if (localAudioUrl) URL.revokeObjectURL(localAudioUrl)
          setLocalAudioUrl(null)
        }}
      />
    ) : null

  return (
    <>
      {dupeModal}
    <form id="upload-form" noValidate onSubmit={handleSubmit}>
      <div className="ru-up-wizard-head">
        <h3>{t(`redesign.upload.${WIZARD_HINTS[wizardStep][0]}`)}</h3>
        <p>{t(`redesign.upload.${WIZARD_HINTS[wizardStep][1]}`)}</p>
      </div>
      <div className="ru-up-step-dots" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={
              i === wizardStep
                ? 'ru-up-step-dot is-active'
                : 'ru-up-step-dot'
            }
          />
        ))}
      </div>

      <AnimatePresence mode="wait">
        <m.div
          key={wizardStep}
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? undefined : { opacity: 0, y: -10 }}
          transition={transition}
        >
          {wizardStep === 0 && (
            <UploadStepAudio
              audioFile={audioFile}
              audioDuration={audioDuration}
              audioDragging={audioDragging}
              onAudioFile={applyAudioFile}
              onDragChange={setAudioDragging}
            />
          )}
          {wizardStep === 1 && (
            <UploadStepDetails
              title={title}
              setTitle={setTitle}
              artist={artist}
              artistMode={artistMode}
              profileArtistName={profileArtistName}
              artistQuery={artistQuery}
              artistOpen={artistOpen}
              artistSearching={artistSearching}
              artistResults={artistResults}
              hasExactArtist={hasExactArtist}
              setArtist={setArtist}
              setArtistMode={setArtistMode}
              setArtistQuery={setArtistQuery}
              setArtistOpen={setArtistOpen}
              genre={genre}
              genreQuery={genreQuery}
              genreOpen={genreOpen}
              genreSearching={genreSearching}
              genreResults={genreResults}
              hasExactGenre={hasExactGenre}
              setGenre={setGenre}
              setGenreQuery={setGenreQuery}
              setGenreOpen={setGenreOpen}
              audioFileLoaded={audioFile !== null}
              lyrics={lyrics}
              onOpenLyricsEditor={() => setShowLyricsEditor(true)}
              isPublic={isPublic}
              setIsPublic={setIsPublic}
              termsAccepted={termsAccepted}
              setTermsAccepted={setTermsAccepted}
              autoDetecting={autoDetecting}
              autoFilled={autoFilled}
              onClearAutoFlag={clearAutoFlag}
            />
          )}
          {wizardStep === 2 && (
            <UploadStepCover
              coverPreview={coverPreview}
              coverDragging={coverDragging}
              onCoverFile={applyCoverFile}
              onCoverClear={clearCover}
              onDragChange={setCoverDragging}
              fromAudioTag={Boolean(autoFilled.cover)}
            />
          )}
          {wizardStep === 3 && (
            <UploadStepPreview
              title={title}
              artistLabel={draftArtistLabel}
              audioDuration={audioDuration}
              coverPreview={coverPreview}
            />
          )}
        </m.div>
      </AnimatePresence>

      {showLyricsEditor && localAudioUrl && (
        <div className="fullscreen-overlay">
          <div className="overlay-content">
            <LyricsEditor
              localAudioUrl={localAudioUrl}
              existingLyrics={lyrics}
              onSaved={(l) => {
                setLyrics(l)
                setShowLyricsEditor(false)
              }}
              onCancel={() => setShowLyricsEditor(false)}
            />
          </div>
        </div>
      )}

      {error && <div className="form-error">{error}</div>}

      <div className="ru-up-wizard-nav">
        <div>
          {wizardStep > 0 && (
            <MotionPress
              type="button"
              variant="ghost"
              disabled={uploading}
              onClick={handleWizardBack}
            >
              {t('redesign.upload.wizardBack')}
            </MotionPress>
          )}
        </div>
        <div>
          {wizardStep < 3 ? (
            <MotionPress
              type="button"
              variant="primary"
              disabled={uploading}
              onClick={handleWizardNext}
            >
              {t('redesign.upload.wizardNext')}
            </MotionPress>
          ) : (
            <MotionPress
              type="submit"
              variant="primary"
              disabled={uploading}
            >
              {t('redesign.upload.wizardSubmit')}
            </MotionPress>
          )}
        </div>
      </div>

      {uploading && (
        <div>
          <div className="progress-bar-wrap">
            <div
              className={`progress-bar-fill${uploadDone ? '' : ' shimmer'}`}
              style={{ width: uploadDone ? '100%' : undefined }}
            />
          </div>
          <p className="progress-label">
            {uploadDone
              ? t('redesign.upload.file.progressProcessing')
              : t('redesign.upload.file.progressUploading')}
          </p>
        </div>
      )}
    </form>
    </>
  )
}
