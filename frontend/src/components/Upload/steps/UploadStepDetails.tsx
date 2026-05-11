import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { hapticNotification, hapticSelection } from '@/lib/telegram'
import type { LyricsResponse } from '@/types/api'
import { UploadComboBox } from './UploadComboBox'

type ArtistMode = 'profile' | 'custom'

export type AutoFilledFields = 'title' | 'artist' | 'genre' | 'cover'

interface Props {
  title: string
  setTitle: (next: string) => void

  artist: string
  artistMode: ArtistMode
  profileArtistName: string | null
  artistQuery: string
  artistOpen: boolean
  artistSearching: boolean
  artistResults: string[]
  hasExactArtist: boolean
  setArtist: (next: string) => void
  setArtistMode: (next: ArtistMode) => void
  setArtistQuery: (next: string) => void
  setArtistOpen: (next: boolean) => void

  genre: string
  genreQuery: string
  genreOpen: boolean
  genreSearching: boolean
  genreResults: string[]
  hasExactGenre: boolean
  setGenre: (next: string) => void
  setGenreQuery: (next: string) => void
  setGenreOpen: (next: boolean) => void

  audioFileLoaded: boolean
  lyrics: LyricsResponse | null
  onOpenLyricsEditor: () => void

  isPublic: boolean
  setIsPublic: (next: boolean) => void
  termsAccepted: boolean
  setTermsAccepted: (next: boolean) => void

  autoDetecting: boolean
  autoFilled: Partial<Record<AutoFilledFields, boolean>>
  onClearAutoFlag: (field: AutoFilledFields) => void
}

export function UploadStepDetails(props: Props) {
  const { t } = useTranslation()

  const {
    title,
    setTitle,
    artist,
    artistMode,
    profileArtistName,
    artistQuery,
    artistOpen,
    artistSearching,
    artistResults,
    hasExactArtist,
    setArtist,
    setArtistMode,
    setArtistQuery,
    setArtistOpen,
    genre,
    genreQuery,
    genreOpen,
    genreSearching,
    genreResults,
    hasExactGenre,
    setGenre,
    setGenreQuery,
    setGenreOpen,
    audioFileLoaded,
    lyrics,
    onOpenLyricsEditor,
    isPublic,
    setIsPublic,
    termsAccepted,
    setTermsAccepted,
    autoDetecting,
    autoFilled,
    onClearAutoFlag,
  } = props

  const renderAutoChip = (
    field: AutoFilledFields,
    onClear: () => void,
  ) => {
    if (!autoFilled[field]) return null
    return (
      <button
        type="button"
        className="ru-up-auto-chip"
        onClick={() => {
          hapticSelection()
          onClear()
          onClearAutoFlag(field)
        }}
        aria-label={t('redesign.upload.file.autoFilledClear')}
      >
        <span>{t('redesign.upload.file.autoFilledHint')}</span>
        <span className="ru-up-auto-chip__sep">·</span>
        <span>{t('redesign.upload.file.autoFilledClear')}</span>
      </button>
    )
  }

  return (
    <>
      {autoDetecting && (
        <div className="ru-up-auto-detecting" role="status">
          {t('redesign.upload.file.autoFilledDetecting')}
        </div>
      )}
      <div className="form-group">
        <div className="ru-up-label-row">
          <label className="form-label" htmlFor="title-input">
            {t('redesign.upload.file.titleLabel')}
          </label>
          {renderAutoChip('title', () => setTitle(''))}
        </div>
        <input
          id="title-input"
          className="form-input"
          type="text"
          placeholder={t('redesign.upload.file.titlePlaceholder')}
          maxLength={256}
          value={title}
          onChange={(e) => {
            setTitle(e.target.value)
            if (autoFilled.title) onClearAutoFlag('title')
          }}
        />
        <span
          className={`ru-up-charcount${
            title.length > 236
              ? title.length >= 256
                ? ' ru-up-charcount--over'
                : ' ru-up-charcount--near'
              : ''
          }`}
        >
          {title.length}/256
        </span>
      </div>

      <div className="form-group genre-search-group">
        <div className="ru-up-label-row">
          <label className="form-label">
            {t('redesign.upload.file.artistLabel')}
          </label>
          {renderAutoChip('artist', () => {
            setArtist('')
            setArtistQuery('')
          })}
        </div>
        <div className="upload-artist-mode">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="selection"
            className={`upload-artist-mode-btn${artistMode === 'profile' ? ' active' : ''}`}
            onClick={() => {
              if (!profileArtistName) {
                hapticNotification('warning')
                return
              }
              setArtistMode('profile')
              setArtist(profileArtistName)
              setArtistQuery(profileArtistName)
              setArtistOpen(false)
              hapticSelection()
            }}
          >
            {t('redesign.upload.file.artistModeProfile')}
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="selection"
            className={`upload-artist-mode-btn${artistMode === 'custom' ? ' active' : ''}`}
            onClick={() => {
              setArtistMode('custom')
              hapticSelection()
            }}
          >
            {t('redesign.upload.file.artistModeCustom')}
          </MotionPress>
        </div>
        {artistMode === 'profile' && (
          <p className="upload-artist-profile-note">
            {profileArtistName
              ? t('redesign.upload.file.artistProfileNote', {
                  name: profileArtistName,
                })
              : t('redesign.upload.file.artistProfileEmpty')}
          </p>
        )}
        {artistMode === 'custom' && (
          <UploadComboBox
            value={artist}
            query={artistQuery}
            open={artistOpen}
            searching={artistSearching}
            results={artistResults}
            hasExact={hasExactArtist}
            toggleHintKey="redesign.upload.file.artistSearchHint"
            inputPlaceholderKey="redesign.upload.file.artistSearchPlaceholder"
            searchProgressKey="redesign.upload.file.artistSearchProgress"
            emptyHintKey="redesign.upload.file.artistSearchEmptyHint"
            createKey="redesign.upload.file.artistCreate"
            onToggleOpen={() => setArtistOpen(!artistOpen)}
            onQueryChange={(next) => {
              setArtistQuery(next)
              if (next.trim()) {
                setArtist(next.trim())
              }
              if (autoFilled.artist) onClearAutoFlag('artist')
            }}
            onPick={(item) => {
              setArtist(item)
              setArtistQuery(item)
              setArtistOpen(false)
              if (autoFilled.artist) onClearAutoFlag('artist')
            }}
            onCreate={(custom) => {
              setArtist(custom)
              setArtistQuery(custom)
              setArtistOpen(false)
              if (autoFilled.artist) onClearAutoFlag('artist')
            }}
          />
        )}
      </div>

      <div className="form-group genre-search-group">
        <div className="ru-up-label-row">
          <label className="form-label">
            {t('redesign.upload.file.genreLabel')}
          </label>
          {renderAutoChip('genre', () => {
            setGenre('')
            setGenreQuery('')
          })}
        </div>
        <UploadComboBox
          value={genre}
          query={genreQuery}
          open={genreOpen}
          searching={genreSearching}
          results={genreResults}
          hasExact={hasExactGenre}
          toggleHintKey="redesign.upload.file.genreSearchHint"
          inputPlaceholderKey="redesign.upload.file.genreSearchPlaceholder"
          searchProgressKey="redesign.upload.file.genreSearchProgress"
          emptyHintKey="redesign.upload.file.genreSearchEmptyHint"
          createKey="redesign.upload.file.genreCreate"
          onToggleOpen={() => setGenreOpen(!genreOpen)}
          onQueryChange={(next) => {
            setGenreQuery(next)
            if (next.trim()) {
              setGenre(next.trim())
            }
            if (autoFilled.genre) onClearAutoFlag('genre')
          }}
          onPick={(item) => {
            setGenre(item)
            setGenreQuery(item)
            setGenreOpen(false)
            if (autoFilled.genre) onClearAutoFlag('genre')
          }}
          onCreate={(custom) => {
            setGenre(custom)
            setGenreQuery(custom)
            setGenreOpen(false)
            if (autoFilled.genre) onClearAutoFlag('genre')
          }}
        />
      </div>

      {audioFileLoaded && (
        <div className="form-group">
          <label className="form-label">
            {t('redesign.upload.file.lyricsLabel')}
          </label>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="selection"
            className={`lyrics-editor-trigger${lyrics ? ' active' : ''}`}
            onClick={() => {
              hapticSelection()
              onOpenLyricsEditor()
            }}
          >
            {lyrics
              ? t('redesign.upload.file.lyricsSet')
              : t('redesign.upload.file.lyricsAdd')}
          </MotionPress>
        </div>
      )}

      <div className="form-group upload-checks">
        <label className="upload-check-row">
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
          />
          <span>{t('redesign.upload.file.visibilityPublic')}</span>
        </label>
        <label className="upload-check-row">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
          />
          <span>
            {t('redesign.upload.file.termsAccept')}
            <a
              href="/legal/upload-rules"
              target="_blank"
              rel="noreferrer"
            >
              {t('redesign.upload.file.termsLink')}
            </a>
            .
          </span>
        </label>
      </div>
    </>
  )
}
