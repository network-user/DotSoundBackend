import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { hapticNotification, hapticSelection } from '@/lib/telegram'
import type { LyricsResponse } from '@/types/api'
import { UploadComboBox } from './UploadComboBox'

type ArtistMode = 'profile' | 'custom'

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
  } = props

  return (
    <>
      <div className="form-group">
        <label className="form-label" htmlFor="title-input">
          {t('redesign.upload.file.titleLabel')}
        </label>
        <input
          id="title-input"
          className="form-input"
          type="text"
          placeholder={t('redesign.upload.file.titlePlaceholder')}
          maxLength={256}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>

      <div className="form-group genre-search-group">
        <label className="form-label">
          {t('redesign.upload.file.artistLabel')}
        </label>
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
            }}
            onPick={(item) => {
              setArtist(item)
              setArtistQuery(item)
              setArtistOpen(false)
            }}
            onCreate={(custom) => {
              setArtist(custom)
              setArtistQuery(custom)
              setArtistOpen(false)
            }}
          />
        )}
      </div>

      <div className="form-group genre-search-group">
        <label className="form-label">
          {t('redesign.upload.file.genreLabel')}
        </label>
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
          }}
          onPick={(item) => {
            setGenre(item)
            setGenreQuery(item)
            setGenreOpen(false)
          }}
          onCreate={(custom) => {
            setGenre(custom)
            setGenreQuery(custom)
            setGenreOpen(false)
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
