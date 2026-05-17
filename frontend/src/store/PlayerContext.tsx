import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { loadHlsClass } from '@/lib/hlsLoader'
import type { HlsPlayer } from '@/lib/hlsLoader'
import { api, getApiErrorMessage, getApiErrorTelemetry } from '@/lib/api'
import { getInternalUserId } from '@/lib/telegram'
import { dismissIsland, showIsland, updateIsland } from '@/lib/island'
import i18n from '@/lib/i18n'
import {
  getCachedAudioUrl,
  getCachedIdsSync,
  isCachedSync,
  markPlayed as markCachePlayed,
  prefetchProgressiveBodyForCache,
  trackProgressiveAudioUrl,
} from '@/lib/offlineCache'
import { queueOrSend } from '@/lib/pendingEvents'
import {
  getThirdPartyStreamOverride,
  inferStreamTypeFromUrl,
} from '@/lib/streamDebugOverride'
import { isBenignPlayError, safePlay } from '@/lib/safePlay'
import { getPrefetchManager } from '@/lib/prefetch/PrefetchManager'
import { shouldUseInternalHlsPlayback } from '@/lib/playbackSourcePolicy'
import { readNetworkSnapshot } from '@/lib/prefetch/network'
import { getHlsQualityPreference } from '@/lib/hlsQualityPreference'
import {
  COVER_RENDER_WIDTHS,
  coverProxyUrl,
} from '@/lib/coverProxy'
import type { StreamResponse, Track } from '@/types/api'
import {
  consumePrefetchedStream as _consumePrefetchedStream,
  tweenVolume as _tweenVolume,
} from '@/store/playerAudioHelpers'

const EQ_FREQUENCIES = [
  32, 64, 125, 250, 500, 1000, 4000, 16000,
]
const EQ_DEFAULT = [0, 0, 0, 0, 0, 0, 0, 0]
const HLS_READY_TIMEOUT_MS = 15000
const MEDIA_SESSION_PLACEHOLDER_SIZES = [192, 512] as const
// Hold the Android system notification "drawer" in the playing state
// across a track switch even if the new audio takes a while to reach
// canplay (cold third_party_stream resolve, slow CDN, large first
// segment). 15s comfortably covers the worst case on 3G while still
// letting a true playback failure surface as paused within reasonable
// time. Prior value 8s was tight and caused the drawer to "blink" on
// metro / weak Wi-Fi when the new track took >5s to start.
const MEDIA_SESSION_SWITCH_HOLD_MS = 15000
// Time-to-live for a pre-resolved stream URL (third_party_stream or
// private). Keeps the URL usable as long as the upstream signed link
// has not expired; we still cross-check ``expires_at`` per item.
const PREFETCHED_STREAM_TTL_MS = 60_000
// How many upcoming tracks we eagerly resolve a stream URL for. 3 is
// the smallest number that survives the typical Android background
// fetch deadline (~30-60 s of suspended network) for two consecutive
// gapless track switches while the screen is locked.
const PREFETCH_STREAM_AHEAD = 3
// Volume tween durations for soft track transitions. 80 ms fade-out
// before src swap removes the click that some Chromium builds emit
// when the audio engine cuts off mid-buffer. 180 ms fade-in after
// canplay smooths the new track in without the abrupt full-volume
// kick that feels like a "jump" between tracks.
const TRACK_FADE_OUT_MS = 80
const TRACK_FADE_IN_MS = 180
// Pro-active refill threshold for the radio queue. When the manual
// queue drops below this many remaining tracks we fire a background
// ``api.getRadio`` to top it up, so the next-track tap never has to
// wait for a fresh network round-trip.
const RADIO_REFILL_THRESHOLD = 5
// "Pseudo-crossfade" lead time. In radio mode, this many ms before
// the current track ends we proactively trigger ``playNext`` so the
// new track starts playing while the previous one is still in its
// fade-out tail. The user perceives an overlap-style transition
// (~1 s) instead of an abrupt onEnded boundary.
//
// NOTE on a *true* crossfade (overlapping two audio sources):
// requires (a) a second ``<audio>`` element, (b) a second
// ``MediaElementAudioSourceNode`` wired into the same EQ chain, and
// (c) listener-set rebinding on every active-audio swap. That is a
// real rewrite of the playback core (1-2 days) and was scoped out
// of this change. Documented under TODO so a follow-up sprint can
// pick it up without re-deriving the design.
const CROSSFADE_LEAD_MS = 2000
// Initial batch size for radio. Bumped from 15 to 25 so a typical
// ~30-minute background listening session can stay self-sufficient
// across an OS-imposed network suspension without tripping the
// in-band refill path.
const RADIO_BATCH_SIZE = 25

type HlsErrorData = {
  type?: unknown
  details?: unknown
  fatal?: unknown
  reason?: unknown
  response?: {
    code?: unknown
    text?: unknown
  }
  error?: {
    message?: unknown
  }
  frag?: {
    url?: unknown
  }
}

function _dbToLinear(db: number) {
  return 10 ** (db / 20)
}

function _computeEqHeadroom(
  bands: number[],
) {
  const positive = bands.filter((v) => v > 0)
  const maxBoost =
    positive.length > 0
      ? Math.max(...positive)
      : 0
  const totalBoost = positive.reduce(
    (sum, value) => sum + value,
    0,
  )
  return Math.min(
    9,
    Math.max(maxBoost * 0.75, totalBoost / 3),
  )
}

function _applyPitchPreservation(
  audio: HTMLAudioElement | null,
) {
  if (!audio) return
  const a = audio as HTMLAudioElement & {
    preservesPitch?: boolean
    mozPreservesPitch?: boolean
    webkitPreservesPitch?: boolean
  }
  try {
    a.preservesPitch = true
    a.mozPreservesPitch = true
    a.webkitPreservesPitch = true
  } catch {
    // older browsers without the property; ignore
  }
}

function _stringOrUndefined(value: unknown) {
  return typeof value === 'string' && value
    ? value
    : undefined
}

function _redactPlaybackUrl(raw: unknown) {
  if (typeof raw !== 'string' || !raw) return undefined
  try {
    const url = new URL(raw)
    return `${url.origin}${url.pathname}${url.search ? '?...' : ''}`
  } catch {
    return raw.split('?')[0] || undefined
  }
}

function _hlsErrorTelemetry(data: HlsErrorData) {
  return {
    type: _stringOrUndefined(data.type),
    details: _stringOrUndefined(data.details),
    fatal: Boolean(data.fatal),
    reason: _stringOrUndefined(data.reason),
    status:
      typeof data.response?.code === 'number'
        ? data.response.code
        : undefined,
    message: _stringOrUndefined(data.error?.message),
    url: _redactPlaybackUrl(data.frag?.url),
  }
}

type HlsErrorTelemetry = ReturnType<typeof _hlsErrorTelemetry>

function _hlsErrorMessage(data: HlsErrorData) {
  const telemetry = _hlsErrorTelemetry(data)
  const detail =
    telemetry.details ||
    telemetry.reason ||
    telemetry.message ||
    'unknown'
  return `HLS playback failed: ${detail}`
}

function _isRecoverableHlsMediaError(
  telemetry: HlsErrorTelemetry,
) {
  return telemetry.type === 'mediaError'
}

function _loadEqState() {
  try {
    const rawBands = localStorage.getItem(
      'player-eq-bands',
    )
    const rawPreset = localStorage.getItem(
      'player-eq-preset',
    )
    const rawBypassed = localStorage.getItem(
      'player-eq-bypassed',
    )
    const bands = rawBands
      ? (JSON.parse(rawBands) as number[])
      : EQ_DEFAULT
    return {
      bands:
        Array.isArray(bands) &&
        bands.length === EQ_DEFAULT.length
          ? bands
          : EQ_DEFAULT,
      preset: rawPreset || 'Flat',
      bypassed: rawBypassed === 'true',
    }
  } catch {
    return {
      bands: EQ_DEFAULT,
      preset: 'Flat',
      bypassed: false,
    }
  }
}

function _saveEqState(
  bands: number[],
  preset: string | null,
  bypassed: boolean,
) {
  localStorage.setItem(
    'player-eq-bands',
    JSON.stringify(bands),
  )
  localStorage.setItem(
    'player-eq-preset',
    preset || 'Flat',
  )
  localStorage.setItem(
    'player-eq-bypassed',
    String(bypassed),
  )
}

interface PlayerContextValue {
  track: Track | null
  isPlaying: boolean
  currentTime: number
  duration: number
  volume: number
  setVolume: (v: number) => void
  isComplaintOpen: boolean
  isCardOpen: boolean
  isLyricsOpen: boolean
  isEqOpen: boolean
  isQueueOpen: boolean
  eqBands: number[]
  eqPreset: string | null
  eqBypassed: boolean
  repeatMode: 'none' | 'one' | 'all'
  shuffleOn: boolean
  hlsError: string | null
  playbackRate: number
  queue: Track[]
  history: Track[]
  radioSessionTimeline: Track[]
  abLoop: { a: number | null; b: number | null }
  toggleRepeat: () => void
  toggleShuffle: () => void
  clearHlsError: () => void
  playTrack: (
    t: Track,
    optsOrUrl?:
      | string
      | { url?: string; contextTracks?: Track[]; preserveQueue?: boolean },
  ) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  seekToSeconds: (sec: number) => void
  skipForward: (s?: number) => void
  skipBackward: (s?: number) => void
  setPlaybackRate: (rate: number) => void
  getPreciseTime: () => number
  playNext: (
    opts?: {
      afterNaturalEnd?: boolean
      bypassInFlightGuard?: boolean
    },
  ) => Promise<boolean>
  playPrev: () => Promise<void>
  playRadioPrevious: () => Promise<boolean>
  setEqBand: (idx: number, gain: number) => void
  setEqPreset: (preset: string | null) => void
  toggleEqBypass: () => void
  resetEq: () => void
  openComplaint: () => void
  closeComplaint: () => void
  openCard: () => void
  closeCard: () => void
  openLyrics: () => void
  closeLyrics: () => void
  openEq: () => void
  closeEq: () => void
  openQueue: () => void
  closeQueue: () => void
  addToQueue: (t: Track) => void
  removeFromQueue: (idx: number) => void
  clearQueue: () => void
  reorderQueue: (from: number, to: number) => void
  setAbA: (sec?: number) => void
  setAbB: (sec?: number) => void
  clearAbLoop: () => void
  stop: () => void
  getAnalyser: () => AnalyserNode | null
  updateTrack: (updated: Partial<Track> & { id: number }) => void
  clearPendingCommentFocus: () => void
  openTrackAtComment: (
    t: Track,
    commentId: number,
  ) => Promise<void>
  radioMode: boolean
  radioSeedTrackId: number | null
  startRadio: (seedTrack: Track) => Promise<void>
  stopRadio: () => void
  sleepMode: 'off' | 'minutes' | 'end-of-track'
  sleepRemainingSec: number
  setSleepTimerMinutes: (minutes: number) => void
  setSleepTimerEndOfTrack: () => void
  cancelSleepTimer: () => void
  isPlayingFromCache: boolean
  trackChangeSlide: {
    bump: number
    dir: 0 | 1 | -1
  }
}

interface PlayerStateValue {
  currentTime: number
  duration: number
  isPlaying: boolean
}

interface PlayerPlaybackValue {
  isPlaying: boolean
  duration: number
}

interface PlayerTimeValue {
  currentTime: number
}

interface PlayerActionsValue {
  playTrack: (
    t: Track,
    optsOrUrl?:
      | string
      | { url?: string; contextTracks?: Track[]; preserveQueue?: boolean },
  ) => Promise<void>
  togglePlay: () => void
  seek: (pct: number) => void
  seekToSeconds: (sec: number) => void
  skipForward: (s?: number) => void
  skipBackward: (s?: number) => void
  setPlaybackRate: (rate: number) => void
  getPreciseTime: () => number
  playNext: (
    opts?: {
      afterNaturalEnd?: boolean
      bypassInFlightGuard?: boolean
    },
  ) => Promise<boolean>
  playPrev: () => Promise<void>
  playRadioPrevious: () => Promise<boolean>
  setVolume: (v: number) => void
  stop: () => void
  setEqBand: (idx: number, gain: number) => void
  setEqPreset: (preset: string | null) => void
  toggleEqBypass: () => void
  resetEq: () => void
  toggleRepeat: () => void
  toggleShuffle: () => void
  clearHlsError: () => void
  openComplaint: () => void
  closeComplaint: () => void
  openCard: () => void
  closeCard: () => void
  openLyrics: () => void
  closeLyrics: () => void
  openEq: () => void
  closeEq: () => void
  openQueue: () => void
  closeQueue: () => void
  addToQueue: (t: Track) => void
  removeFromQueue: (idx: number) => void
  clearQueue: () => void
  reorderQueue: (from: number, to: number) => void
  setAbA: (sec?: number) => void
  setAbB: (sec?: number) => void
  clearAbLoop: () => void
  getAnalyser: () => AnalyserNode | null
  updateTrack: (updated: Partial<Track> & { id: number }) => void
  clearPendingCommentFocus: () => void
  openTrackAtComment: (
    t: Track,
    commentId: number,
  ) => Promise<void>
  radioMode: boolean
  radioSeedTrackId: number | null
  startRadio: (seedTrack: Track) => Promise<void>
  stopRadio: () => void
  sleepMode: 'off' | 'minutes' | 'end-of-track'
  sleepRemainingSec: number
  setSleepTimerMinutes: (minutes: number) => void
  setSleepTimerEndOfTrack: () => void
  cancelSleepTimer: () => void
}

interface PlayerMetaValue {
  track: Track | null
  volume: number
  isComplaintOpen: boolean
  isCardOpen: boolean
  isLyricsOpen: boolean
  isEqOpen: boolean
  isQueueOpen: boolean
  eqBands: number[]
  eqPreset: string | null
  eqBypassed: boolean
  repeatMode: 'none' | 'one' | 'all'
  shuffleOn: boolean
  hlsError: string | null
  playbackRate: number
  queue: Track[]
  history: Track[]
  radioSessionTimeline: Track[]
  abLoop: { a: number | null; b: number | null }
  pendingCommentFocus: {
    trackId: number
    commentId: number
  } | null
  isPlayingFromCache: boolean
  trackChangeSlide: {
    bump: number
    dir: 0 | 1 | -1
  }
}

const PlayerStateCtx = createContext<PlayerStateValue | null>(null)
const PlayerPlaybackCtx =
  createContext<PlayerPlaybackValue | null>(null)
const PlayerTimeCtx =
  createContext<PlayerTimeValue | null>(null)
const PlayerActionsCtx = createContext<PlayerActionsValue | null>(null)
const PlayerMetaCtx = createContext<PlayerMetaValue | null>(null)

const PlayerContext =
  createContext<PlayerContextValue | null>(null)

const _SAVE_INTERVAL = 5000

/** Min interval between React time updates (progress, lyrics UI). */
const PLAYER_UI_TIME_MS = 40

const _PLAYER_SNAPSHOT_KEY = 'player-snapshot'
const _PLAYER_LEGACY_TRACK_KEY = 'player-track'
const _PLAYER_LEGACY_TIME_KEY = 'player-time'

type _PlayerSnapshotV2 = {
  v: 2
  track: Track
  time: number
  queue?: Track[]
  savedAt?: number
}

const _QUEUE_PERSIST_MAX = 100
const _QUEUE_PERSIST_TTL_MS = 7 * 24 * 60 * 60 * 1000

const _RADIO_STATE_KEY = 'player-radio-state'

function _saveRadioState(
  mode: boolean,
  seedTrackId: number | null,
): void {
  try {
    if (mode && seedTrackId != null) {
      sessionStorage.setItem(
        _RADIO_STATE_KEY,
        JSON.stringify({ mode, seedTrackId }),
      )
    } else {
      sessionStorage.removeItem(_RADIO_STATE_KEY)
    }
  } catch {
    /* quota / private mode */
  }
}

function _loadRadioState(): {
  mode: true
  seedTrackId: number
} | null {
  try {
    const raw = sessionStorage.getItem(_RADIO_STATE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as {
      mode?: boolean
      seedTrackId?: number
    }
    if (
      parsed?.mode === true &&
      typeof parsed.seedTrackId === 'number' &&
      Number.isInteger(parsed.seedTrackId) &&
      parsed.seedTrackId > 0
    ) {
      return { mode: true, seedTrackId: parsed.seedTrackId }
    }
  } catch {
    /* ignore */
  }
  return null
}

function _cloneTrackForStorage(t: Track): Track {
  const { resume_position_seconds: _r, ...rest } = t
  return rest as Track
}

function _saveState(
  t: Track | null,
  s: number,
  queue?: Track[],
) {
  if (!t) return
  const time = Number.isFinite(s) ? s : 0
  try {
    const payload: _PlayerSnapshotV2 = {
      v: 2,
      track: _cloneTrackForStorage(t),
      time,
      savedAt: Date.now(),
    }
    if (queue && queue.length > 0) {
      payload.queue = queue
        .slice(0, _QUEUE_PERSIST_MAX)
        .map(_cloneTrackForStorage)
    }
    localStorage.setItem(
      _PLAYER_SNAPSHOT_KEY,
      JSON.stringify(payload),
    )
    localStorage.removeItem(_PLAYER_LEGACY_TRACK_KEY)
    localStorage.removeItem(_PLAYER_LEGACY_TIME_KEY)
  } catch {
    /* quota / private mode */
  }
}

function _loadState(): {
  track: Track | null
  time: number
  queue?: Track[]
} {
  try {
    const snapRaw = localStorage.getItem(
      _PLAYER_SNAPSHOT_KEY,
    )
    if (snapRaw) {
      const snap = JSON.parse(snapRaw) as {
        v?: number
        track?: Track
        time?: number
        queue?: Track[]
        savedAt?: number
      }
      const looksValid =
        (snap?.v === 1 || snap?.v === 2) &&
        !!snap.track &&
        typeof snap.track.id === 'number' &&
        typeof snap.time === 'number' &&
        Number.isFinite(snap.time)
      if (looksValid) {
        let queue: Track[] | undefined
        if (
          snap.v === 2 &&
          Array.isArray(snap.queue) &&
          snap.queue.length > 0
        ) {
          const fresh =
            typeof snap.savedAt !== 'number' ||
            Date.now() - snap.savedAt < _QUEUE_PERSIST_TTL_MS
          if (fresh) {
            queue = snap.queue.filter(
              (t: Track | null | undefined): t is Track =>
                t != null && typeof t.id === 'number',
            )
          }
        }
        return {
          track: snap.track as Track,
          time: snap.time as number,
          queue,
        }
      }
    }

    const r = localStorage.getItem(
      _PLAYER_LEGACY_TRACK_KEY,
    )
    if (!r) return { track: null, time: 0 }
    const track = JSON.parse(r) as Track
    const time = parseFloat(
      localStorage.getItem(_PLAYER_LEGACY_TIME_KEY) ||
        '0',
    )
    const safeTime = Number.isFinite(time) ? time : 0
    if (
      typeof track?.id === 'number' &&
      Number.isFinite(safeTime)
    ) {
      try {
        const migrated: _PlayerSnapshotV2 = {
          v: 2,
          track: _cloneTrackForStorage(track),
          time: safeTime,
          savedAt: Date.now(),
        }
        localStorage.setItem(
          _PLAYER_SNAPSHOT_KEY,
          JSON.stringify(migrated),
        )
        localStorage.removeItem(
          _PLAYER_LEGACY_TRACK_KEY,
        )
        localStorage.removeItem(
          _PLAYER_LEGACY_TIME_KEY,
        )
      } catch {
        /* keep legacy keys if migrate fails */
      }
    }
    return { track, time: safeTime }
  } catch {
    return { track: null, time: 0 }
  }
}

function _clearState() {
  localStorage.removeItem(_PLAYER_SNAPSHOT_KEY)
  localStorage.removeItem(_PLAYER_LEGACY_TRACK_KEY)
  localStorage.removeItem(_PLAYER_LEGACY_TIME_KEY)
}

function _mediaSessionAssetUrl(fileName: string): string {
  const base = import.meta.env.BASE_URL || '/'
  const prefix = base.endsWith('/') ? base : `${base}/`
  return new URL(`${prefix}${fileName}`, window.location.origin).href
}

function _mediaSessionArtwork(track: Track): MediaImage[] {
  if (track.cover_key) {
    return COVER_RENDER_WIDTHS.map((width) => ({
      src: new URL(
        coverProxyUrl(track.cover_key!, { width }),
        window.location.origin,
      ).href,
      sizes: `${width}x${width}`,
      type: 'image/webp',
    }))
  }
  return MEDIA_SESSION_PLACEHOLDER_SIZES.map((size) => ({
    src: _mediaSessionAssetUrl(
      `media-session-placeholder-${size}.png`,
    ),
    sizes: `${size}x${size}`,
    type: 'image/png',
  }))
}

function _setMediaSessionActionHandler(
  action: MediaSessionAction,
  handler: MediaSessionActionHandler | null,
) {
  try {
    navigator.mediaSession.setActionHandler(action, handler)
  } catch {}
}

function _updateMediaSession(
  track: Track,
  audio: HTMLAudioElement,
  onNext: () => void,
  onPrev: () => void,
) {
  if (!('mediaSession' in navigator)) return
  try {
    navigator.mediaSession.metadata =
      new MediaMetadata({
        title: track.title,
        artist: track.artist || '',
        artwork: _mediaSessionArtwork(track),
      })
    navigator.mediaSession.playbackState = audio.paused
      ? 'paused'
      : 'playing'
    _setMediaSessionActionHandler(
      'play',
      () => {
        void safePlay(audio)
      },
    )
    _setMediaSessionActionHandler(
      'pause',
      () => audio.pause(),
    )
    _setMediaSessionActionHandler(
      'nexttrack',
      onNext,
    )
    _setMediaSessionActionHandler(
      'previoustrack',
      onPrev,
    )
    _setMediaSessionActionHandler(
      'seekto',
      (d) => {
        if (
          d.seekTime !== undefined &&
          audio.duration
        )
          audio.currentTime = d.seekTime
      },
    )
    _setMediaSessionActionHandler(
      'seekforward',
      (d) => {
        const offset = d.seekOffset ?? 15
        const target = Math.min(
          (audio.duration || 0) - 0.5,
          (audio.currentTime || 0) + offset,
        )
        if (Number.isFinite(target) && target >= 0) {
          audio.currentTime = target
        }
      },
    )
    _setMediaSessionActionHandler(
      'seekbackward',
      (d) => {
        const offset = d.seekOffset ?? 15
        const target = Math.max(
          0,
          (audio.currentTime || 0) - offset,
        )
        audio.currentTime = target
      },
    )
  } catch {}
}

function _updatePositionState(
  a: HTMLAudioElement,
) {
  if (
    !('mediaSession' in navigator) ||
    !a.duration
  )
    return
  try {
    navigator.mediaSession.setPositionState({
      duration: a.duration,
      playbackRate: a.playbackRate,
      position: a.currentTime,
    })
  } catch {}
}

// Push a position-state to the system notification drawer using the
// track's known ``duration_seconds`` even before ``audio.duration``
// becomes a real number. Without this, the first ~500 ms after a
// track switch the drawer keeps showing the *previous* track's
// progress (or a frozen scrubber on Android), which the user reads
// as "the player got stuck". Called both right at the start of a
// switch and again after the audio has metadata ready.
function _pushPositionStateForTrack(
  audio: HTMLAudioElement,
  track: Track,
) {
  if (!('mediaSession' in navigator)) return
  const realDuration = Number.isFinite(audio.duration)
    ? audio.duration
    : 0
  const fallbackDuration =
    typeof track.duration_seconds === 'number' &&
    Number.isFinite(track.duration_seconds) &&
    track.duration_seconds > 0
      ? track.duration_seconds
      : 0
  const duration = realDuration > 0 ? realDuration : fallbackDuration
  if (duration <= 0) return
  const position = Number.isFinite(audio.currentTime)
    ? Math.min(audio.currentTime, duration)
    : 0
  const playbackRate = Number.isFinite(audio.playbackRate)
    ? audio.playbackRate
    : 1
  try {
    navigator.mediaSession.setPositionState({
      duration,
      playbackRate,
      position: Math.max(0, position),
    })
  } catch {
    // setPositionState throws on weird inputs in some older Chromium
    // builds; the drawer just loses the scrubber for one frame, no
    // user-visible regression beyond what we already had.
  }
}

// _consumePrefetchedStream / _tweenVolume / PrefetchedStreamRecord
// are re-exported from ``@/store/playerAudioHelpers`` (imported at
// the top of this file). They live in their own module so unit
// tests can import them without dragging in the entire React
// PlayerContext.

// iOS audio session: tell Safari we are a playback (not transient,
// not voice-call) audio source. This is the iOS counterpart to
// Android's wake-lock + media foreground service. Without it Safari
// (Mobile + iPad PWA) treats the WebView like a banner-ad audio
// source: it ducks under voice notes, gets cut by the next ringtone,
// and can be silently suspended once the screen locks.
//
// Shipped in Safari 18.4+ (March 2025); on older builds the API
// does not exist and we no-op silently.
type AudioSessionLike = {
  type?: 'auto' | 'playback' | 'transient' | 'transient-solo' | 'ambient' | 'play-and-record'
}
function _setIosAudioSessionToPlayback() {
  if (typeof navigator === 'undefined') return
  const session = (
    navigator as Navigator & { audioSession?: AudioSessionLike }
  ).audioSession
  if (!session) return
  try {
    session.type = 'playback'
  } catch {
    // Some webviews ship the property but throw when set; treat as
    // a no-op so we don't crash the player on a feature-detect.
  }
}

// Wake Lock API: ask the OS to keep the screen wake-lock acquired
// while audio is playing. On Android Chrome PWAs (``display:
// 'standalone'``) this is the closest we can get to a "media
// foreground service" without an Android-native shell -- it
// noticeably extends how long the PWA process stays alive after the
// user locks the phone with a track playing. On iOS / older browsers
// the API does not exist; we no-op silently.
//
// Why screen-type only:
// * ``screen`` is the only type currently shipped in stable Chromium.
// * The hypothetical ``system`` type is an experiment behind a flag
//   and not exposed to the document. There is no safe way to ask for
//   "keep the audio session alive" beyond what a playing
//   ``HTMLAudioElement`` + an active ``mediaSession`` already give us.
type WakeLockSentinelLike = {
  released?: boolean
  release: () => Promise<void>
  addEventListener: (type: 'release', listener: () => void) => void
}
type WakeLockNavigator = Navigator & {
  wakeLock?: {
    request: (type: 'screen') => Promise<WakeLockSentinelLike>
  }
}

let _wakeLockSentinel: WakeLockSentinelLike | null = null
let _wakeLockRequestInFlight = false

async function _acquireWakeLock() {
  if (typeof navigator === 'undefined') return
  const nav = navigator as WakeLockNavigator
  if (!nav.wakeLock || typeof nav.wakeLock.request !== 'function') {
    return
  }
  if (_wakeLockSentinel || _wakeLockRequestInFlight) return
  _wakeLockRequestInFlight = true
  try {
    const sentinel = await nav.wakeLock.request('screen')
    _wakeLockSentinel = sentinel
    sentinel.addEventListener('release', () => {
      if (_wakeLockSentinel === sentinel) {
        _wakeLockSentinel = null
      }
    })
  } catch {
    // The request can fail if the page is no longer visible (the
    // user already locked their phone before the request landed) --
    // there is nothing we can do beyond letting the next ``play``
    // event re-attempt the acquisition.
  } finally {
    _wakeLockRequestInFlight = false
  }
}

function _releaseWakeLock() {
  const sentinel = _wakeLockSentinel
  if (!sentinel) return
  _wakeLockSentinel = null
  try {
    void sentinel.release()
  } catch {
    /* sentinel already released; ignore */
  }
}

// Kick off a pre-warm for the artwork URLs the next ``setMetadata``
// call is going to use. The browser fetches the bitmap, the SW cache
// (``covers-cache``) ends up populated, and by the time the actual
// MediaSession update happens, the system UI gets a fully cached
// image and does not flash a blank tile. Side effect only -- we do
// not await any of this.
function _warmCoverArtwork(track: Track) {
  if (typeof Image === 'undefined') return
  const artwork = _mediaSessionArtwork(track)
  for (const item of artwork) {
    try {
      const img = new Image()
      img.decoding = 'async'
      img.loading = 'eager'
      img.src = item.src
    } catch {
      // ignore -- best-effort prefetch, never block the switch
    }
  }
}

export function PlayerProvider({
  children,
}: {
  children: ReactNode
}) {
  const initialEqRef = useRef(_loadEqState())
  const audioRef = useRef<HTMLAudioElement>(null)
  const hlsRef = useRef<HlsPlayer | null>(null)
  const prefetchCacheRef = useRef<{
    forTrackId: number
    tracks: Track[]
  } | null>(null)
  const historyRef = useRef<Track[]>([])
  const wantResumeAfterCardCloseRef = useRef(false)
  // ---------------------------------------------------------------
  // PREFETCH SUBSYSTEMS MAP (responsibility chart)
  //
  // The player keeps five distinct prefetch / preload mechanisms, each
  // pulling on a different layer of the playback stack. Until they
  // are unified into a single PrefetchManager (TODO under "Унификация
  // prefetch подсистем" in TODO.md), this comment is the canonical
  // map of what owns what.
  //
  //  1. ``prefetchAudioRef`` (HTMLAudioElement)
  //     - Layer: browser HTTP cache.
  //     - Triggered by: track-change effect.
  //     - For: progressive-audio (direct MP3) tracks of the *next*
  //       likely track. We assign ``src = next-progressive-url`` to
  //       a hidden ``<audio>`` element which makes the browser
  //       issue a Range request and warm its HTTP cache. The
  //       primary audio reuses that warm cache when the user actually
  //       switches.
  //     - Lifetime: 1 in-flight slot at a time.
  //
  //  2. ``preloadHlsRef`` + ``preloadHlsTrackIdRef``
  //     - Layer: hls.js manifest+segment cache.
  //     - Triggered by: track-change effect, only for HLS tracks.
  //     - For: pre-fetching the HLS playlist + first segment of the
  //       next likely track via a *detached* hls.js instance, so a
  //       swap on the main audio gets canplay almost immediately.
  //     - Lifetime: 1 detached HlsPlayer; destroyed and re-created
  //       per next-track guess.
  //
  //  3. ``prefetchedStreamsRef`` (Map<trackId, PrefetchedStreamRecord>)
  //     - Layer: backend stream resolution (the one round-trip
  //       ``api.getStream`` we cannot avoid for ``third_party_stream``
  //       and private tracks).
  //     - Triggered by: track-change effect.
  //     - For: pre-resolving the actual playable URL for the
  //       *next* ``PREFETCH_STREAM_AHEAD`` tracks. Crucial for
  //       background playback robustness: the OS will throttle
  //       fetches once the screen is locked, so resolving in the
  //       foreground means a queue of ready-to-play URLs that need
  //       no network at switch time.
  //     - Lifetime: per-trackId; consumed by ``_consumePrefetchedStream``.
  //       TTL = ``PREFETCHED_STREAM_TTL_MS``.
  //
  //  4. ``swCachePrefetchAbortRef`` + ``swCachePrefetchSecondAbortRef``
  //     - Layer: service-worker cache (workbox runtimeCaching).
  //     - Triggered by: track-change effect; AbortController-based
  //       cancellation when the next-track guess changes.
  //     - For: explicit ``fetch()`` of upcoming HLS manifests +
  //       first-segment URLs against the same origin so that the
  //       service-worker route in ``vite.config.ts`` populates the
  //       ``hls-manifest-cache`` / ``hls-segment-cache`` /
  //       ``progressive-audio-cache`` / (added in this change)
  //       ``radio-cache`` and ``track-queue-cache``.
  //     - Lifetime: per next-track guess; aborted on guess change.
  //
  //  5. ``getPrefetchManager()`` (singleton in @/lib/prefetch)
  //     - Layer: cross-feature prefetch orchestration (covers,
  //       low-priority assets, hint hooks).
  //     - Triggered by: ``markPlaybackStart``, ``enqueue`` calls
  //       throughout the player.
  //     - For: anything that does NOT belong to the four
  //       ref-driven mechanisms above (cover-art warmups, queue
  //       enqueue hints, idle-time prefetches).
  //
  // Why five separate mechanisms exist:
  // each lives at a different stack layer (browser HTTP cache,
  // hls.js memory, backend round-trip cache, service-worker cache,
  // generic cross-feature manager) and has its own lifecycle. The
  // intent of the unification TODO is to keep the *layers* but
  // expose them through a single entry point with shared "next-
  // candidate" computation, rather than four independent
  // useEffects each guessing what the next track will be.
  // ---------------------------------------------------------------
  const prefetchAudioRef =
    useRef<HTMLAudioElement | null>(null)
  const manualQueueRef = useRef<Track[]>([])
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamExpiresAtRef = useRef<number | null>(null)
  const lastStreamUrlRef = useRef<string | null>(null)
  const lastTrackIdRef = useRef<number | null>(null)
  const lastHlsFatalTelemetryRef = useRef<{
    key: string
    atMs: number
  } | null>(null)
  const streamLoadFailedTrackIdRef = useRef<
    number | null
  >(null)
  const unavailableTrackIdsRef = useRef<Set<number>>(new Set())
  const lastPlaybackErrorRef = useRef<{
    trackId: number | null
    message: string | null
    atMs: number
  }>({
    trackId: null,
    message: null,
    atMs: 0,
  })
  const srcAssignedAtRef = useRef<number>(0)
  const playSessionRef = useRef(0)
  const preloadHlsRef = useRef<HlsPlayer | null>(null)
  const preloadHlsTrackIdRef = useRef<number | null>(
    null,
  )
  const swCachePrefetchAbortRef = useRef<AbortController | null>(null)
  const swCachePrefetchTrackIdRef = useRef<number | null>(null)
  const swCachePrefetchSecondAbortRef = useRef<AbortController | null>(null)
  // Pre-resolved stream URLs for the next ``PREFETCH_STREAM_AHEAD``
  // probable tracks. Populated by the prefetch effect for tracks that
  // need a backend round-trip on every play (third_party_stream and
  // private). Keyed by trackId so playTrack can look up by id no
  // matter which slot in the queue the user actually swiped to.
  //
  // Why a Map and not just "the next track":
  // when the PWA goes to the background on Android, the OS will
  // suspend any in-flight fetch after ~30-60 s. If the only resolved
  // URL was for the very next track, the *second* and *third* track
  // switch in the background hits a network request that fails or
  // hangs, audio goes silent, the system kills the process, and the
  // notification drawer disappears (the user-reported "plays 1-2
  // songs in the background then dies"). Prefetching the URLs for
  // n+1..n+3 while we are still in foreground keeps the playback
  // chain unbroken across the OS-imposed background fetch deadline.
  const prefetchedStreamsRef = useRef<
    Map<
      number,
      {
        trackId: number
        url: string
        streamType: 'direct' | 'hls'
        expiresAt: number | null
        resolvedAt: number
      }
    >
  >(new Map())
  const audioCtxRef =
    useRef<AudioContext | null>(null)
  const filtersRef = useRef<BiquadFilterNode[]>([])
  const eqBandsRef = useRef<number[]>(
    initialEqRef.current.bands,
  )
  const eqBypassedRef = useRef(
    initialEqRef.current.bypassed,
  )
  const postEqGainRef =
    useRef<GainNode | null>(null)
  const sourceRef =
    useRef<MediaElementAudioSourceNode | null>(
      null,
    )
  const eqLoadPromiseRef = useRef<Promise<void> | null>(
    null,
  )
  const eqLoadedRef = useRef(false)
  const eqSaveTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    )
  const lastEqPayloadRef = useRef(
    JSON.stringify({
      preset: initialEqRef.current.preset,
      bands: initialEqRef.current.bands,
    }),
  )

  const [track, setTrack] = useState<Track | null>(
    () => _loadState().track,
  )
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const currentTimeRef = useRef(0)
  useEffect(() => {
    currentTimeRef.current = currentTime
  }, [currentTime])
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(() => {
    const s = localStorage.getItem('player-volume')
    const n = s == null ? Number.NaN : Number(s)
    return Number.isFinite(n) ? n : 0.8
  })
  const [isComplaintOpen, setIsComplaintOpen] =
    useState(false)
  const [isCardOpen, setIsCardOpen] = useState(false)
  const [isLyricsOpen, setIsLyricsOpen] =
    useState(false)
  const [isEqOpen, setIsEqOpen] = useState(false)
  const [isQueueOpen, setIsQueueOpen] = useState(false)
  const [pendingCommentFocus, setPendingCommentFocus] =
    useState<{
      trackId: number
      commentId: number
    } | null>(null)
  const [playbackRate, setPlaybackRateState] =
    useState(1)
  const [queue, setQueue] = useState<Track[]>([])
  const [history, setHistory] = useState<Track[]>([])
  const [abLoop, setAbLoop] = useState<{
    a: number | null
    b: number | null
  }>({ a: null, b: null })
  const abLoopRef = useRef<{
    a: number | null
    b: number | null
  }>({ a: null, b: null })
  const [eqBands, setEqBands] =
    useState<number[]>(
      initialEqRef.current.bands,
    )
  const [eqPreset, setEqPresetState] =
    useState<string | null>(
      initialEqRef.current.preset,
    )
  const [eqBypassed, setEqBypassed] =
    useState(initialEqRef.current.bypassed)
  const [repeatMode, setRepeatMode] = useState<'none' | 'one' | 'all'>(
    () => (localStorage.getItem('player-repeat') as 'none' | 'one' | 'all') ?? 'none',
  )
  const [shuffleOn, setShuffleOn] = useState(
    () => localStorage.getItem('player-shuffle') === 'true',
  )
  const [hlsError, setHlsError] = useState<string | null>(null)
  const [isPlayingFromCache, setIsPlayingFromCache] = useState(false)
  const [sleepMode, setSleepMode] = useState<
    'off' | 'minutes' | 'end-of-track'
  >('off')
  const [sleepRemainingSec, setSleepRemainingSec] = useState(0)
  const sleepDeadlineRef = useRef<number | null>(null)
  const sleepEndOfTrackRef = useRef(false)
  const [radioMode, setRadioMode] = useState(false)
  const [radioSeedTrackId, setRadioSeedTrackId] = useState<number | null>(null)
  const radioModeRef = useRef(false)
  const radioSeedTrackIdRef = useRef<number | null>(null)
  const radioPlayedIdsRef = useRef<Set<number>>(new Set())
  const radioSessionTimelineRef = useRef<Track[]>([])
  const [radioSessionTimeline, setRadioSessionTimeline] = useState<
    Track[]
  >([])
  const playTrackSlideInjectRef = useRef<1 | -1 | null>(null)
  const playNextInFlightRef = useRef(false)
  const mediaSessionSwitchHoldUntilRef = useRef(0)
  // Tracks whether the pseudo-crossfade early ``playNext`` has
  // already been fired for the *currently-loaded* trackId. Reset
  // on every track change so the next track gets its own chance to
  // trigger an early transition.
  const crossfadeFiredForRef = useRef<number | null>(null)
  // Records when we entered ``playTrack`` for a given trackId, so
  // the first ``playing`` event can compute "time from user-visible
  // tap/swipe to first audible frame" and emit it as telemetry.
  // Distinct from ``tt_canplay_ms`` in
  // ``recordPlaybackSourceTelemetry``: that one measures "time from
  // src assigned to canplay", which excludes the network resolves
  // (``api.getStream``, ``api.getRadio`` refill) that happen before
  // ``audio.src = newUrl``. The end-to-end number is what the user
  // actually feels, and is what the radio prefetch + wake-lock
  // tweaks aim to bring down.
  const playSwitchStartedAtRef = useRef<{
    trackId: number
    ts: number
    surface: 'radio' | 'player'
  } | null>(null)
  const [trackChangeSlide, setTrackChangeSlide] = useState<{
    bump: number
    dir: 0 | 1 | -1
  }>({ bump: 0, dir: 0 })
  const repeatModeRef = useRef<'none' | 'one' | 'all'>(
    (localStorage.getItem('player-repeat') as 'none' | 'one' | 'all') ?? 'none',
  )
  const shuffleOnRef = useRef(localStorage.getItem('player-shuffle') === 'true')

  const playCountSentRef = useRef(false)
  const listenSignalSentRef = useRef(false)
  const listenStartTimeRef = useRef(0)
  const restoredRef = useRef(false)
  const playerTimeUiLastRef = useRef(0)

  const beginMediaSessionSwitchHold = (
    audio: HTMLAudioElement,
    nextTrack: Track,
  ) => {
    if (!('mediaSession' in navigator)) return
    if (!track || track.id === nextTrack.id || audio.paused) return
    mediaSessionSwitchHoldUntilRef.current =
      Date.now() + MEDIA_SESSION_SWITCH_HOLD_MS
    try {
      navigator.mediaSession.playbackState = 'playing'
    } catch {}
  }

  const isMediaSessionSwitchHeld = () =>
    mediaSessionSwitchHoldUntilRef.current > Date.now()

  const finishMediaSessionSwitch = (
    nextTrack: Track,
    audio: HTMLAudioElement,
  ) => {
    mediaSessionSwitchHoldUntilRef.current = 0
    _updateMediaSession(
      nextTrack,
      audio,
      () => playNext(),
      () => playPrev(),
    )
  }

  const applyEqBands = useCallback(
    (
      bands: number[] = eqBandsRef.current,
      bypassed: boolean = eqBypassedRef.current,
    ) => {
      for (const [
        index,
        filter,
      ] of filtersRef.current.entries()) {
        filter.gain.value = bypassed
          ? 0
          : bands[index] ?? 0
      }

      const out = postEqGainRef.current
      if (out) {
        const headroomDb = bypassed
          ? 0
          : _computeEqHeadroom(bands)
        out.gain.value = _dbToLinear(-headroomDb)
      }
    },
    [],
  )

  const loadEqSettings = useCallback(
    async (force = false) => {
      const uid = getInternalUserId()
      if (!uid) return

      if (
        !force &&
        eqLoadPromiseRef.current
      ) {
        await eqLoadPromiseRef.current
        return
      }

      if (
        eqLoadedRef.current &&
        !force
      ) {
        return
      }

      const promise = api
        .getEqSettings()
        .then((data) => {
          if (data?.bands?.length !== 8) return
          const nextBands = data.bands.map((value) =>
            Number(value),
          )
          const nextPreset =
            data.preset || 'Flat'
          eqBandsRef.current = nextBands
          lastEqPayloadRef.current = JSON.stringify({
            preset: nextPreset,
            bands: nextBands,
          })
          setEqBands(nextBands)
          setEqPresetState(nextPreset)
        })
        .catch(() => {})
        .finally(() => {
          eqLoadedRef.current = true
          eqLoadPromiseRef.current = null
        })

      eqLoadPromiseRef.current = promise
      await promise
    },
    [],
  )

  const setEqPreset = useCallback(
    (preset: string | null) => {
      setEqPresetState(preset)
    },
    [],
  )

  const toggleEqBypass = useCallback(() => {
    setEqBypassed((prev) => !prev)
  }, [])

  const resetEq = useCallback(() => {
    setEqBands(EQ_DEFAULT)
    setEqPresetState('Flat')
    setEqBypassed(false)
  }, [])

  const resumeAudioOutput = useCallback(() => {
    const ctx = audioCtxRef.current
    if (ctx && ctx.state === 'suspended') {
      void ctx.resume()
    }
  }, [])

  const requestPlayback = useCallback(
    (
      audio: HTMLAudioElement,
      opts?: Parameters<typeof safePlay>[1],
    ) => {
      resumeAudioOutput()
      return safePlay(audio, opts)
    },
    [resumeAudioOutput],
  )

  const _initAudioCtx = useCallback(() => {
    const audio = audioRef.current
    if (!audio || audioCtxRef.current) return
    audio.crossOrigin = 'anonymous'
    const perfLite =
      typeof document !== 'undefined' &&
      document.body.classList.contains('ds-perf-lite')
    const ctx = new AudioContext()
    audioCtxRef.current = ctx
    const src = ctx.createMediaElementSource(audio)
    sourceRef.current = src

    const filters = EQ_FREQUENCIES.map((freq) => {
      const f = ctx.createBiquadFilter()
      f.type = 'peaking'
      f.frequency.value = freq
      f.Q.value = 1.4
      f.gain.value = 0
      return f
    })
    filtersRef.current = filters

    const out = ctx.createGain()
    postEqGainRef.current = out

    const analyser = ctx.createAnalyser()
    analyser.fftSize = perfLite ? 128 : 256
    analyser.smoothingTimeConstant = perfLite
      ? 0.88
      : 0.86
    analyserRef.current = analyser

    let prev: AudioNode = src
    for (const f of filters) {
      prev.connect(f)
      prev = f
    }
    prev.connect(out)
    out.connect(ctx.destination)
    out.connect(analyser)
    applyEqBands()
  }, [applyEqBands])

  const setEqBand = useCallback(
    (idx: number, gain: number) => {
      setEqBands((prev) => {
        const next = [...prev]
        next[idx] = gain
        return next
      })
    },
    [],
  )

  useEffect(() => {
    eqBandsRef.current = eqBands
    eqBypassedRef.current = eqBypassed
    applyEqBands()
    _saveEqState(
      eqBands,
      eqPreset,
      eqBypassed,
    )
  }, [
    applyEqBands,
    eqBands,
    eqPreset,
    eqBypassed,
  ])

  useEffect(() => {
    void loadEqSettings()
  }, [loadEqSettings])

  useEffect(() => {
    if (!isEqOpen) return
    void loadEqSettings(true)
  }, [isEqOpen, loadEqSettings])

  useEffect(() => {
    const uid = getInternalUserId()
    if (!uid || !eqLoadedRef.current) return

    const payload = JSON.stringify({
      preset: eqPreset,
      bands: eqBands,
    })
    if (payload === lastEqPayloadRef.current) {
      return
    }

    if (eqSaveTimerRef.current) {
      clearTimeout(eqSaveTimerRef.current)
    }
    eqSaveTimerRef.current = setTimeout(() => {
      api
        .saveEqSettings({
          preset: eqPreset,
          bands: eqBands,
        })
        .then(() => {
          lastEqPayloadRef.current =
            payload
        })
        .catch(() => {})
    }, 800)

    return () => {
      if (eqSaveTimerRef.current) {
        clearTimeout(eqSaveTimerRef.current)
      }
    }
  }, [eqBands, eqPreset])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || restoredRef.current) return
    restoredRef.current = true
    const saved = _loadState()
    const savedRadio = _loadRadioState()
    if (savedRadio) {
      radioModeRef.current = true
      radioSeedTrackIdRef.current = savedRadio.seedTrackId
      setRadioMode(true)
      setRadioSeedTrackId(savedRadio.seedTrackId)
    }
    if (saved.queue && saved.queue.length > 0) {
      manualQueueRef.current = [...saved.queue]
      setQueue([...saved.queue])
    }
    if (saved.track) {
      let restoredTrack: Track = saved.track
      let restoredTime: number = saved.time
      const isOffline =
        typeof navigator !== 'undefined' &&
        navigator.onLine === false
      if (isOffline) {
        const cached = getCachedIdsSync()
        if (cached.size > 0 && !cached.has(saved.track.id)) {
          const fromQueue = (saved.queue ?? []).find((t) =>
            cached.has(t.id),
          )
          if (fromQueue) {
            restoredTrack = fromQueue
            restoredTime = 0
            manualQueueRef.current =
              manualQueueRef.current.filter(
                (t) => t.id !== fromQueue.id,
              )
            setQueue([...manualQueueRef.current])
          }
        }
      }
      setTrack(restoredTrack)
      lastTrackIdRef.current = restoredTrack.id
      audio.crossOrigin = 'anonymous'
      audio.volume = volume

      const seekAfterLoad = () => {
        if (restoredTime > 0) {
          setCurrentTime(restoredTime)
          const onMeta = () => {
            audio.currentTime = restoredTime
            audio.removeEventListener(
              'loadedmetadata',
              onMeta,
            )
          }
          audio.addEventListener(
            'loadedmetadata',
            onMeta,
          )
        }
      }

      void (async () => {
        const cachedUrl = await getCachedAudioUrl(
          restoredTrack.id,
        )
        if (cachedUrl) {
          srcAssignedAtRef.current = Date.now()
          audio.src = cachedUrl
          seekAfterLoad()
          return
        }
        if (isOffline) {
          // Не пытаемся достучаться до сети — оставим
          // плеер с восстановленным треком, но без src.
          return
        }
        if (
          restoredTrack.access_mode === 'official_embed' ||
          restoredTrack.access_mode === 'external_link'
        ) {
          return
        }
        if (
          restoredTrack.access_mode === 'third_party_stream' ||
          !restoredTrack.is_public
        ) {
          api.getStream(restoredTrack.id)
            .then(async (stream) => {
              srcAssignedAtRef.current = Date.now()
              const HlsMod = await loadHlsClass()
              if (
                stream.stream_type === 'hls' &&
                HlsMod.isSupported()
              ) {
                await startHlsPlayback(
                  audio,
                  stream.url,
                  undefined,
                  false,
                  restoredTrack.id,
                )
              } else {
                audio.src = stream.url
              }
              seekAfterLoad()
            })
            .catch(() => {})
        } else {
          const fallback = trackProgressiveAudioUrl(
            restoredTrack.id,
          )

          if (shouldUseInternalHlsPlayback(restoredTrack)) {
            const HlsMod = await loadHlsClass()
            const hlsUrl = (
              `/api/v1/tracks/${restoredTrack.id}/hls/master.m3u8`
            )
            srcAssignedAtRef.current = Date.now()
            if (HlsMod.isSupported()) {
              startHlsPlayback(
                audio,
                hlsUrl,
                fallback,
                false,
                restoredTrack.id,
              )
                .then(seekAfterLoad)
                .catch(() => {})
            } else {
              audio.src = fallback
              seekAfterLoad()
            }
          } else {
            srcAssignedAtRef.current = Date.now()
            audio.src = fallback
            seekAfterLoad()
          }
        }
      })()
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (audio) audio.volume = volume
    localStorage.setItem(
      'player-volume',
      volume.toString(),
    )
  }, [volume])

  useEffect(() => {
    if (!track) return
    const i = setInterval(() => {
      const a = audioRef.current
      if (
        a &&
        lastTrackIdRef.current === track.id &&
        Number.isFinite(a.currentTime)
      ) {
        _saveState(
          track,
          a.currentTime,
          manualQueueRef.current,
        )
      }
    }, _SAVE_INTERVAL)
    return () => clearInterval(i)
  }, [track])

  useEffect(() => {
    if (!track) return
    const handle = window.setTimeout(() => {
      _saveState(
        track,
        audioRef.current?.currentTime ?? 0,
        manualQueueRef.current,
      )
    }, 500)
    return () => window.clearTimeout(handle)
  }, [track, queue])

  useEffect(() => {
    if (!track) return
    const onBeforeUnload = () => {
      const a = audioRef.current
      _saveState(
        track,
        a?.currentTime ?? 0,
        manualQueueRef.current,
      )
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [track])

  // Wake Lock + AudioContext recovery on visibility change. The OS
  // automatically releases the wake-lock the moment the document
  // becomes hidden; when it comes back to visible (user unlocks the
  // phone, switches back into the PWA) we have to re-request it for
  // the lock to keep being effective. AudioContext can also slide
  // into ``suspended`` after a long background interval -- resume it
  // here so the EQ chain is alive again.
  useEffect(() => {
    if (typeof document === 'undefined') return
    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return
      const a = audioRef.current
      if (!a || a.paused) return
      void _acquireWakeLock()
      const ctx = audioCtxRef.current
      if (ctx && ctx.state === 'suspended') {
        void ctx.resume().catch(() => {})
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () =>
      document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  const toggleRepeat = useCallback(() => {
    setRepeatMode((prev) => {
      const next = prev === 'none' ? 'one' : prev === 'one' ? 'all' : 'none'
      repeatModeRef.current = next
      localStorage.setItem('player-repeat', next)
      return next
    })
  }, [])

  const toggleShuffle = useCallback(() => {
    setShuffleOn((prev) => {
      shuffleOnRef.current = !prev
      localStorage.setItem('player-shuffle', String(!prev))
      return !prev
    })
  }, [])

  const clearHlsError = useCallback(() => setHlsError(null), [])

  const setVolume = (v: number) =>
    setVolumeState(Math.max(0, Math.min(1, v)))

  const isSoundCloudUnavailableError = useCallback(
    (errorMessage: string) => {
      const msg = errorMessage.toLowerCase()
      return (
        msg.includes('no streamable format') ||
        msg.includes('sc track missing url') ||
        msg.includes('private track') ||
        msg.includes('track is private') ||
        msg.includes('deleted') ||
        msg.includes('removed') ||
        msg.includes('no longer available') ||
        msg.includes('soundcloud stream unavailable')
      )
    },
    [],
  )

  const isSoundCloudUnavailableTrack = useCallback(
    (candidate: Track) => {
      if (candidate.access_mode !== 'third_party_stream') {
        return false
      }
      return (
        candidate.source_platform === 'soundcloud' ||
        candidate.source === 'soundcloud' ||
        Boolean(candidate.sc_url)
      )
    },
    [],
  )

  const markTrackUnavailableInSession = useCallback(
    (trackId: number) => {
      unavailableTrackIdsRef.current.add(trackId)
      manualQueueRef.current = manualQueueRef.current.filter(
        (item) => item.id !== trackId,
      )
      setQueue([...manualQueueRef.current])
      const cache = prefetchCacheRef.current
      if (!cache) return
      prefetchCacheRef.current = {
        forTrackId: cache.forTrackId,
        tracks: cache.tracks.filter(
          (item) => item.id !== trackId,
        ),
      }
    },
    [],
  )

  // Auto-skip chain control. consecutiveAutoSkipsRef counts how many tracks
  // were skipped in a row WITHOUT a successful playback in between. The
  // counter resets when onPlay fires (real playback started). When the
  // counter reaches MAX_CONSECUTIVE_AUTO_SKIPS we stop the cascade and show
  // a final error so the UI doesn't churn forever on a broken queue.
  const MAX_CONSECUTIVE_AUTO_SKIPS = 3
  const MAX_RADIO_AUTO_SKIPS_PER_SESSION = 7
  const consecutiveAutoSkipsRef = useRef(0)
  const radioAutoSkipsRef = useRef(0)
  const radioAutoSkipHaltedRef = useRef(false)
  type PlaybackFailureTelemetry = {
    errorCode?: string
    errorReason?: string
    userMessage?: string
  }
  const lastUnavailableFailureRef =
    useRef<PlaybackFailureTelemetry>({})

  // Toast dedup: when a burst of skips happens, collapse them into a single
  // "Пропущено N недоступных треков" island that updates in place.
  const unavailableSkipBatchRef = useRef<{
    count: number
    islandId: string | null
    resetTimer: ReturnType<typeof setTimeout> | null
  }>({ count: 0, islandId: null, resetTimer: null })

  const flushUnavailableSkipBatch = useCallback(() => {
    const b = unavailableSkipBatchRef.current
    if (b.resetTimer != null) {
      clearTimeout(b.resetTimer)
    }
    if (b.islandId) {
      // Let the existing island time out naturally; just detach our handle.
    }
    unavailableSkipBatchRef.current = {
      count: 0,
      islandId: null,
      resetTimer: null,
    }
  }, [])

  const recordUnavailableSkip = useCallback(
    (userMessage?: string) => {
      const b = unavailableSkipBatchRef.current
      b.count += 1
      const trimmedUserMessage = userMessage?.trim() || ''
      const title =
        b.count === 1
          ? (trimmedUserMessage ||
              i18n.t('redesign.playerErrors.trackUnavailable'))
          : i18n.t(
              'redesign.playerErrors.tracksUnavailableSkipped',
              { count: b.count },
            )
      if (b.islandId) {
        updateIsland(b.islandId, { title })
      } else {
        b.islandId = showIsland({
          kind: 'toast',
          title,
          durationMs: 5000,
        })
      }
      if (b.resetTimer != null) {
        clearTimeout(b.resetTimer)
      }
      b.resetTimer = setTimeout(() => {
        unavailableSkipBatchRef.current = {
          count: 0,
          islandId: null,
          resetTimer: null,
        }
      }, 3500)
    },
    [],
  )

  const haltRadioAfterAutoSkipExhaustion = useCallback(() => {
    radioAutoSkipHaltedRef.current = true
    radioAutoSkipsRef.current = 0
    consecutiveAutoSkipsRef.current = 0
    lastUnavailableFailureRef.current = {}
    radioSessionTimelineRef.current = []
    setRadioSessionTimeline([])
    radioModeRef.current = false
    radioSeedTrackIdRef.current = null
    setRadioMode(false)
    setRadioSeedTrackId(null)
    _saveRadioState(false, null)
    manualQueueRef.current = []
    setQueue([])
    playNextInFlightRef.current = false
    playTrackSlideInjectRef.current = null
    playSessionRef.current += 1
    const audio = audioRef.current
    if (audio) {
      try {
        audio.pause()
      } catch {
        /* ignore */
      }
      try {
        audio.removeAttribute('src')
        audio.load()
      } catch {
        /* ignore */
      }
    }
    setIsPlaying(false)
  }, [])

  // Component-scoped helper used by both onError and playTrack. Returns
  // true if the cascade advanced, false if the safety limit kicked in.
  const skipUnavailableTrack = async (
    trackId: number,
    failure: PlaybackFailureTelemetry = {},
  ): Promise<boolean> => {
    const wasRadioMode = radioModeRef.current
    if (wasRadioMode && radioAutoSkipHaltedRef.current) {
      return false
    }
    if (
      failure.errorCode ||
      failure.errorReason ||
      failure.userMessage
    ) {
      lastUnavailableFailureRef.current = failure
    }
    markTrackUnavailableInSession(trackId)
    recordUnavailableSkip(failure.userMessage)
    consecutiveAutoSkipsRef.current += 1
    if (wasRadioMode) {
      radioAutoSkipsRef.current += 1
    }
    if (
      consecutiveAutoSkipsRef.current >= MAX_CONSECUTIVE_AUTO_SKIPS ||
      (wasRadioMode &&
        radioAutoSkipsRef.current >= MAX_RADIO_AUTO_SKIPS_PER_SESSION)
    ) {
      const consecutiveSkips = consecutiveAutoSkipsRef.current
      const radioSessionSkips = radioAutoSkipsRef.current
      const radioSeedTrackId = radioSeedTrackIdRef.current
      const queueSize = manualQueueRef.current.length
      const failureTelemetry = lastUnavailableFailureRef.current
      consecutiveAutoSkipsRef.current = 0
      const b = unavailableSkipBatchRef.current
      if (b.islandId) dismissIsland(b.islandId)
      flushUnavailableSkipBatch()
      if (wasRadioMode) {
        void queueOrSend(
          'client-telemetry',
          '/api/v1/signals/client/playback-event',
          {
            event_name: 'radio_auto_skip_exhausted',
            surface: 'radio',
            current_track_id: trackId,
            radio_seed_track_id: radioSeedTrackId,
            consecutive_skips: Math.max(
              consecutiveSkips,
              radioSessionSkips,
            ),
            queue_size: queueSize,
            error_code: failureTelemetry.errorCode,
            error_reason: failureTelemetry.errorReason,
          },
          { silent: true },
        )
      }
      haltRadioAfterAutoSkipExhaustion()
      showIsland({
        kind: 'error',
        title: i18n.t('redesign.playerErrors.noPlayableTracks'),
        durationMs: 4200,
      })
      return false
    }
    return await playNext({ bypassInFlightGuard: true })
  }

  const pendingPlaybackErrorRef = useRef<number | null>(null)

  const showPlaybackErrorOnce = useCallback(
    (trackId: number | null, title: string) => {
      const now = Date.now()
      const last = lastPlaybackErrorRef.current
      const isDuplicate =
        last.trackId === trackId &&
        last.message === title &&
        now - last.atMs < 2500
      if (isDuplicate) {
        return
      }
      lastPlaybackErrorRef.current = {
        trackId,
        message: title,
        atMs: now,
      }
      if (pendingPlaybackErrorRef.current != null) {
        window.clearTimeout(pendingPlaybackErrorRef.current)
      }
      pendingPlaybackErrorRef.current = window.setTimeout(() => {
        pendingPlaybackErrorRef.current = null
        const a = audioRef.current
        if (!a) return
        if (trackId !== null && lastTrackIdRef.current !== trackId) {
          return
        }
        if (!a.paused && a.currentTime > 0.15 && !a.error) {
          return
        }
        showIsland({
          kind: 'error',
          title,
          durationMs: 3600,
        })
      }, 2500)
    },
    [],
  )

  const startDirectPlayback = useCallback(
    async (
      audio: HTMLAudioElement,
      url: string,
    ) => {
      setHlsError(null)
      audio.crossOrigin = 'anonymous'
      srcAssignedAtRef.current = Date.now()
      audio.src = url
      audio.volume = volume
      await requestPlayback(audio)
    },
    [requestPlayback, volume],
  )

  const recordPlaybackSourceTelemetry = useCallback(
    (
      audio: HTMLAudioElement,
      trackId: number,
      chosenSource:
        | 'hls'
        | 'progressive'
        | 'third_party_stream'
        | 'cached',
    ) => {
      // Fire-and-forget signal that records which playback path was
      // selected for this track switch and how long it took to reach
      // canplay. Backed by ``client_playback_event`` so we get the
      // same Prometheus counter + structured log other client signals
      // already use; no new endpoint, no new schema migration.
      const startedAt =
        typeof performance !== 'undefined' &&
        typeof performance.now === 'function'
          ? performance.now()
          : Date.now()
      const network = readNetworkSnapshot()
      let sent = false
      const send = (canplayAt: number | null) => {
        if (sent) return
        sent = true
        cleanup()
        if (lastTrackIdRef.current !== trackId) return
        const ttMs =
          canplayAt != null
            ? Math.max(0, Math.round(canplayAt - startedAt))
            : null
        void queueOrSend(
          'client-telemetry',
          '/api/v1/signals/client/playback-event',
          {
            event_name: 'playback_source_chosen',
            surface: radioModeRef.current ? 'radio' : 'player',
            current_track_id: trackId,
            chosen_source: chosenSource,
            tt_canplay_ms: ttMs,
            effective_type: network.effectiveType,
            save_data: network.saveData,
            downlink_mbps: network.downlinkMbps,
          },
          { silent: true },
        )
      }
      const onReady = () => {
        const t =
          typeof performance !== 'undefined' &&
          typeof performance.now === 'function'
            ? performance.now()
            : Date.now()
        send(t)
      }
      const cleanup = () => {
        audio.removeEventListener('canplay', onReady)
        audio.removeEventListener('playing', onReady)
        if (timeoutId != null) {
          window.clearTimeout(timeoutId)
        }
      }
      audio.addEventListener('canplay', onReady, { once: true })
      audio.addEventListener('playing', onReady, { once: true })
      const timeoutId = window.setTimeout(() => {
        // Don't leak listeners forever; if the track never reaches
        // canplay (network stall, fatal error before fallback), we
        // still want a row in telemetry to surface the failure rate.
        send(null)
      }, 30_000)
    },
    [],
  )

  const recordHlsFatalTelemetry = useCallback(
    (
      trackId: number | null | undefined,
      telemetry: HlsErrorTelemetry,
    ) => {
      const effectiveTrackId = trackId ?? lastTrackIdRef.current
      const key = [
        effectiveTrackId ?? 'none',
        telemetry.type ?? '',
        telemetry.details ?? '',
        telemetry.status ?? '',
        telemetry.url ?? '',
      ].join('|')
      const now = Date.now()
      const last = lastHlsFatalTelemetryRef.current
      if (last?.key === key && now - last.atMs < 30_000) return
      lastHlsFatalTelemetryRef.current = { key, atMs: now }
      void queueOrSend(
        'client-telemetry',
        '/api/v1/signals/client/playback-event',
        {
          event_name: 'hls_fatal_error',
          surface: radioModeRef.current ? 'radio' : 'player',
          current_track_id: effectiveTrackId ?? undefined,
          hls_type: telemetry.type,
          hls_details: telemetry.details,
          hls_reason: telemetry.reason,
          hls_status: telemetry.status,
          hls_fatal: telemetry.fatal,
          hls_message: telemetry.message,
          hls_url: telemetry.url,
        },
        { silent: true },
      )
    },
    [],
  )

  const startHlsPlayback = useCallback(
    async (
      audio: HTMLAudioElement,
      sourceUrl: string,
      fallbackUrl?: string,
      autoplay = true,
      trackId?: number | null,
    ) => {
      const Hls = await loadHlsClass()
      const qualityPref = getHlsQualityPreference()
      return new Promise<void>((resolve, reject) => {
        let settled = false
        let readyTimer: number | null = null
        const hls = new Hls({
          enableWorker: true,
          // -1 = ABR auto. With ``testBandwidth: false`` hls.js skips
          // the bandwidth-probe fragment dance that otherwise adds an
          // extra round-trip before playback. Combined with our 4s
          // segments this trims time-to-first-frame to a single TS
          // segment (~150 KB) on the hot path.
          startLevel: -1,
          testBandwidth: false,
          // Fast handshake on slow links: shorter per-fragment timeout
          // means a stuck CDN trips the recovery path early instead
          // of pinning the user on a 20 s default timeout.
          fragLoadingTimeOut: 8000,
          manifestLoadingTimeOut: 5000,
          levelLoadingTimeOut: 5000,
          // Buffer enough to hide a temporary stall but not so much
          // that aggressive seeking causes the engine to refetch
          // 10+ segments on every scrub.
          maxBufferLength: 30,
          maxMaxBufferLength: 60,
          maxBufferSize: 60 * 1000 * 1000,
          maxBufferHole: 0.5,
          // Pre-fetch the next fragment as soon as the current one
          // finishes downloading; this is what kills "stutter on the
          // segment boundary" perceived by users on edge networks.
          startFragPrefetch: true,
          // Keep ABR snappy: smaller EWMA windows react to a network
          // drop within 2-3 segments instead of 6-8.
          abrEwmaFastLive: 1.0,
          abrEwmaSlowLive: 3.0,
          abrEwmaFastVoD: 1.0,
          abrEwmaSlowVoD: 3.0,
        })
        const onReady = () => {
          if (settled) return
          settled = true
          cleanupReady()
          setHlsError(null)
          audio.volume = volume
          if (autoplay) void requestPlayback(audio)
          resolve()
        }
        const cleanupReady = () => {
          audio.removeEventListener('canplay', onReady)
          audio.removeEventListener('playing', onReady)
          hls.off(Hls.Events.FRAG_BUFFERED, onReady)
          if (readyTimer != null) {
            window.clearTimeout(readyTimer)
            readyTimer = null
          }
        }
        const _applyQualityPin = () => {
          if (qualityPref === 'auto') return
          const levels = hls.levels
          if (!Array.isArray(levels) || levels.length === 0) return
          const want = qualityPref === 'hi' ? 'hi' : 'lo'
          for (let i = 0; i < levels.length; i += 1) {
            const lvl = levels[i] as { url?: readonly string[] }
            const urls = lvl?.url ?? []
            if (urls.some((u) => u.includes(`/${want}/`))) {
              try {
                hls.currentLevel = i
              } catch {
                /* level pinning is best-effort */
              }
              return
            }
          }
        }
        const startFallback = () => {
          const resumeAt = Number.isFinite(audio.currentTime)
            ? audio.currentTime
            : 0
          hls.destroy()
          hlsRef.current = null
          audio.crossOrigin = 'anonymous'
          if (resumeAt > 0) {
            const restorePosition = () => {
              try {
                audio.currentTime = Math.min(
                  resumeAt,
                  Math.max(0, (audio.duration || resumeAt + 1) - 1),
                )
              } catch {
                /* ignore */
              }
            }
            audio.addEventListener(
              'loadedmetadata',
              restorePosition,
              { once: true },
            )
          }
          audio.src = fallbackUrl || ''
          audio.volume = volume
          if (autoplay) void requestPlayback(audio)
        }
        const failBeforeReady = (message: string) => {
          if (settled) return
          settled = true
          cleanupReady()
          if (fallbackUrl) {
            setHlsError(null)
            startFallback()
            resolve()
          } else {
            reject(new Error(message))
          }
        }
        hlsRef.current = hls
        hls.loadSource(sourceUrl)
        hls.attachMedia(audio)
        hls.on(
          Hls.Events.MANIFEST_PARSED,
          () => {
            audio.volume = volume
            _applyQualityPin()
          },
        )
        hls.on(Hls.Events.FRAG_BUFFERED, onReady)
        audio.addEventListener('canplay', onReady, { once: true })
        audio.addEventListener('playing', onReady, { once: true })
        readyTimer = window.setTimeout(() => {
          const message = 'HLS playback failed: startup timeout'
          setHlsError(message)
          failBeforeReady(message)
        }, HLS_READY_TIMEOUT_MS)
        hls.on(Hls.Events.ERROR, (_e, d) => {
          const telemetry = _hlsErrorTelemetry(d)
          if (!d.fatal) {
            console.debug('dotsound:hls_nonfatal_error', telemetry)
            return
          }
          const message = _hlsErrorMessage(d)
          console.warn('dotsound:hls_fatal_error', telemetry)
          if (
            fallbackUrl &&
            _isRecoverableHlsMediaError(telemetry)
          ) {
            setHlsError(null)
            if (!settled) {
              settled = true
              cleanupReady()
              startFallback()
              resolve()
              return
            }
            startFallback()
            return
          }
          recordHlsFatalTelemetry(trackId, telemetry)
          if (settled) {
            if (fallbackUrl) {
              setHlsError(null)
              startFallback()
              return
            }
            setHlsError(message)
            return
          }
          setHlsError(message)
          failBeforeReady(message)
        })
      })
    },
    [recordHlsFatalTelemetry, requestPlayback, volume],
  )

  const rebindThirdPartyStream = useCallback(
    async (
      tr: Track,
      audio: HTMLAudioElement,
      atSec: number,
    ) => {
      if (tr.access_mode !== 'third_party_stream') return
      if (hlsRef.current) {
        try {
          hlsRef.current.destroy()
        } catch {
          /* */
        }
        hlsRef.current = null
      }
      const stream = await api.getStream(tr.id)
      if (!stream?.url) return
      lastStreamUrlRef.current = stream.url
      streamExpiresAtRef.current = stream.expires_in
        ? Date.now() + stream.expires_in * 1000
        : null
      if (stream.stream_type === 'hls') {
        const HlsMod = await loadHlsClass()
        if (HlsMod.isSupported()) {
          await startHlsPlayback(
            audio,
            stream.url,
            undefined,
            false,
            tr.id,
          )
          const afterReady = () => {
            if (atSec > 0.25) {
              try {
                audio.currentTime = atSec
              } catch {
                /* */
              }
            }
            void requestPlayback(audio)
          }
          if (audio.readyState >= 2) {
            afterReady()
          } else {
            audio.addEventListener('canplay', afterReady, {
              once: true,
            })
          }
          return
        }
      }
      audio.crossOrigin = 'anonymous'
      audio.src = stream.url
      audio.volume = volume
      const onReady = () => {
        if (atSec > 0.25) {
          try {
            audio.currentTime = atSec
          } catch {
            /* */
          }
        }
        void requestPlayback(audio)
      }
      if (audio.readyState >= 2) {
        onReady()
      } else {
        audio.addEventListener('canplay', onReady, {
          once: true,
        })
      }
    },
    [requestPlayback, startHlsPlayback, volume],
  )

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const sendListenSignal = () => {
      if (
        listenSignalSentRef.current ||
        !track ||
        track.id <= 0
      )
        return
      const listened = Math.floor(
        audio.currentTime - listenStartTimeRef.current,
      )
      if (listened <= 0) return
      listenSignalSentRef.current = true
      void queueOrSend(
        'record-listen',
        '/api/v1/signals/listen',
        {
          track_id: track.id,
          duration_listened: listened,
          total_duration: track.duration_seconds,
          source_context: 'player',
          last_position: Math.max(
            0,
            Math.floor(audio.currentTime),
          ),
        },
      )
    }

    const onPlay = () => {
      mediaSessionSwitchHoldUntilRef.current = 0
      setIsPlaying(true)
      setCurrentTime(audio.currentTime)
      playerTimeUiLastRef.current = performance.now()
      // Real playback started — reset auto-skip cascade guard so the
      // next failure starts a fresh attempt count.
      consecutiveAutoSkipsRef.current = 0
      flushUnavailableSkipBatch()
      if ('mediaSession' in navigator)
        navigator.mediaSession.playbackState = 'playing'
      _updatePositionState(audio)
      // Emit end-to-end track-switch latency: from the moment
      // playTrack was invoked (typically the user gesture) to the
      // first ``playing`` event of the new audio. Fired exactly
      // once per switch -- the ref is consumed below so a later
      // pause/resume on the same track does not re-trigger it.
      const switchStart = playSwitchStartedAtRef.current
      if (
        switchStart &&
        track &&
        switchStart.trackId === track.id
      ) {
        playSwitchStartedAtRef.current = null
        const nowMs =
          typeof performance !== 'undefined' &&
          typeof performance.now === 'function'
            ? performance.now()
            : Date.now()
        const latencyMs = Math.max(
          0,
          Math.round(nowMs - switchStart.ts),
        )
        const network = readNetworkSnapshot()
        void queueOrSend(
          'client-telemetry',
          '/api/v1/signals/client/playback-event',
          {
            event_name: 'track_switch_latency',
            surface: switchStart.surface,
            current_track_id: track.id,
            tt_first_play_ms: latencyMs,
            effective_type: network.effectiveType,
            save_data: network.saveData,
            downlink_mbps: network.downlinkMbps,
          },
          { silent: true },
        )
      }
      // Hold the OS wake-lock so the PWA process stays a media-
      // playback session for as long as we're actually playing.
      // Without this Android can suspend the WebView ~60-90 s after
      // the screen goes off and the notification drawer disappears
      // with the process (the user-reported "plays 1-2 songs in the
      // background then dies").
      void _acquireWakeLock()
      // iOS Safari 18+ counterpart: declare the audio session as
      // ``playback`` so the OS treats us as a music app for ducking
      // and lock-screen handover.
      _setIosAudioSessionToPlayback()
      if (audioCtxRef.current?.state === 'suspended')
        audioCtxRef.current.resume()
      if (
        !playCountSentRef.current &&
        track &&
        track.id > 0
      ) {
        playCountSentRef.current = true
        if (!api.hasSession()) {
          void queueOrSend(
            'post-play',
            `/api/v1/tracks/${track.id}/play`,
            {},
          )
        }
      }
      listenSignalSentRef.current = false
      listenStartTimeRef.current =
        audio.currentTime
    }
    const onPause = () => {
      setIsPlaying(false)
      setCurrentTime(audio.currentTime)
      playerTimeUiLastRef.current = performance.now()
      if ('mediaSession' in navigator)
        navigator.mediaSession.playbackState = isMediaSessionSwitchHeld()
          ? 'playing'
          : 'paused'
      _updatePositionState(audio)
      // Only release the wake-lock when the pause is *real* (user
      // pause / end-of-queue) -- a pause caused by an in-flight
      // track switch must keep the lock so the OS does not suspend
      // the WebView mid-swap.
      if (!isMediaSessionSwitchHeld()) {
        _releaseWakeLock()
      }
      sendListenSignal()
    }
    const onEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
      sendListenSignal()
      if (sleepEndOfTrackRef.current) {
        sleepEndOfTrackRef.current = false
        sleepDeadlineRef.current = null
        setSleepMode('off')
        setSleepRemainingSec(0)
        return
      }
      const audio = audioRef.current
      if (repeatModeRef.current === 'one' && audio) {
        audio.currentTime = 0
        void requestPlayback(audio)
        return
      }
      const doNext = () => {
        playNext({ afterNaturalEnd: true }).then((played) => {
          if (
            !played &&
            repeatModeRef.current === 'all' &&
            audioRef.current &&
            track
          ) {
            const cur = audioRef.current
            cur.currentTime = 0
            void requestPlayback(cur)
          }
        })
      }
      // Always advance immediately. Previously we delayed the
      // radio advance by 1.5 s when the next track was not warm
      // yet, which made the gap between tracks *worse* on slow
      // networks (extra 1.5 s of silence on top of the buffering
      // gap). With the prefetched-stream-url + cover-warm + drawer
      // hold tweaks the new track now starts loading in parallel
      // with the previous one ending, so the right answer is "go
      // now and let the audio element buffer in the background".
      doNext()
    }
      const onError = () => {
      const a = audioRef.current
      if (!a || !track) return
      const code = a.error?.code
      if (code === MediaError.MEDIA_ERR_ABORTED) return
      if (!a.paused && a.currentTime > 0) return
      const effectiveSrc = `${a.currentSrc || a.src || ''}`.trim()
      if (!effectiveSrc) return
      if (
        (code === MediaError.MEDIA_ERR_NETWORK ||
          code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) &&
        track.access_mode === 'third_party_stream'
      ) {
        const t = a.currentTime
        void rebindThirdPartyStream(
          track,
          a,
          t,
        ).catch(async (err) => {
          const message = getApiErrorMessage(
            err,
            i18n.t('redesign.playerErrors.playback'),
          )
          const telemetry = getApiErrorTelemetry(err)
          if (
            isSoundCloudUnavailableTrack(track) &&
            isSoundCloudUnavailableError(message)
          ) {
            await skipUnavailableTrack(track.id, telemetry)
            return
          }
          showPlaybackErrorOnce(track.id, message)
          await skipUnavailableTrack(track.id, telemetry)
        })
        return
      }
      if (
        code === MediaError.MEDIA_ERR_NETWORK ||
        code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED
      ) {
        const expires = streamExpiresAtRef.current
        if (
          expires &&
          Date.now() > expires - 30_000 &&
          !track.is_public
        ) {
          api
            .getStream(track.id)
            .then((stream) => {
              if (a && stream?.url) {
                const t = a.currentTime
                a.src = stream.url
                a.currentTime = t
                void requestPlayback(a)
                streamExpiresAtRef.current =
                  stream.expires_in
                    ? Date.now() +
                      stream.expires_in * 1000
                    : null
                lastStreamUrlRef.current = stream.url
              }
            })
            .catch(async (err) => {
              await skipUnavailableTrack(
                track.id,
                getApiErrorTelemetry(err),
              )
            })
          return
        }
      }
      void skipUnavailableTrack(track.id, {
        errorCode:
          typeof code === 'number'
            ? `media_error_${code}`
            : 'media_error',
        errorReason: 'browser_media_error',
      })
    }
    const onStalled = () => {
      try {
        showIsland({
          kind: 'toast',
          title: i18n.t('redesign.playerErrors.buffering'),
          durationMs: 1800,
        })
      } catch {
        /* ignore */
      }
      // Auto-recover: a "stalled" event after a seek typically means
      // hls.js is waiting on a fragment that has not arrived yet. Kick
      // the loader at the current playhead so the engine cancels the
      // pending fetch and starts a new one targeted at the seek point.
      // For native progressive playback the audio element re-issues a
      // Range request when the readyState drops; we just nudge it by
      // re-asserting currentTime once the network is alive again.
      try {
        const hls = hlsRef.current
        if (hls) {
          try {
            hls.stopLoad()
            hls.startLoad(audio.currentTime)
          } catch {
            /* hls.js missing or destroyed */
          }
          return
        }
        if (audio.readyState < 2 && audio.networkState !== 3) {
          // re-poke the playhead so the browser re-issues a Range
          const t = audio.currentTime
          if (Number.isFinite(t)) {
            audio.currentTime = t
          }
        }
      } catch {
        /* never let recovery itself crash the player */
      }
    }
    const _maybeTriggerPseudoCrossfade = (
      a: HTMLAudioElement,
    ) => {
      if (!radioModeRef.current) return
      if (a.paused) return
      const dur = a.duration
      if (!Number.isFinite(dur) || dur <= 0) return
      const remainingMs = (dur - a.currentTime) * 1000
      if (
        remainingMs <= 0 ||
        remainingMs > CROSSFADE_LEAD_MS
      ) {
        return
      }
      const currentId = track?.id ?? lastTrackIdRef.current ?? null
      if (currentId == null) return
      if (crossfadeFiredForRef.current === currentId) return
      // Only fire if there is actually something to cross-fade to,
      // so we don't preempt the natural ``onEnded`` for the last
      // track of a finite queue.
      const nextInQueue = manualQueueRef.current[0]
      if (!nextInQueue) return
      // Don't compete with an in-flight ``playNext`` (e.g. from a
      // user swipe that just landed) -- that would double-advance.
      if (playNextInFlightRef.current) return
      crossfadeFiredForRef.current = currentId
      void playNext({ afterNaturalEnd: true })
    }

    const onTime = () => {
      const ab = abLoopRef.current
      if (
        ab.a !== null &&
        ab.b !== null &&
        ab.b > ab.a &&
        audio.currentTime >= ab.b
      ) {
        audio.currentTime = ab.a
        playerTimeUiLastRef.current = 0
      }
      const now = performance.now()
      if (
        now - playerTimeUiLastRef.current <
        PLAYER_UI_TIME_MS
      ) {
        return
      }
      playerTimeUiLastRef.current = now
      const t = audio.currentTime
      setCurrentTime(t)
      // Note: ``setPositionState`` is *not* called here per
      // timeupdate. The browser extrapolates the scrubber from the
      // last position+playbackRate snapshot, so feeding it 4 times
      // per second causes drawer-side micro-stutter on Android
      // Chromium without any UX benefit. We push fresh snapshots
      // only on play/pause/ratechange/seeked/durationchange below.
      _maybeTriggerPseudoCrossfade(audio)
    }
    const onDur = () => {
      setDuration(audio.duration || 0)
      _updatePositionState(audio)
    }
    const onSeeked = () => {
      _updatePositionState(audio)
    }
    const onRateChange = () => {
      _updatePositionState(audio)
    }

    audio.addEventListener('play', onPlay)
    audio.addEventListener('pause', onPause)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('durationchange', onDur)
    audio.addEventListener('seeked', onSeeked)
    audio.addEventListener('ratechange', onRateChange)
    audio.addEventListener('error', onError)
    audio.addEventListener('stalled', onStalled)

    if (track) {
      _updateMediaSession(
        track,
        audio,
        () => playNext(),
        () => playPrev(),
      )
    }

    return () => {
      audio.removeEventListener('play', onPlay)
      audio.removeEventListener('pause', onPause)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('durationchange', onDur)
      audio.removeEventListener('seeked', onSeeked)
      audio.removeEventListener('ratechange', onRateChange)
      audio.removeEventListener('error', onError)
      audio.removeEventListener('stalled', onStalled)
    }
  }, [
    track,
    requestPlayback,
    rebindThirdPartyStream,
    isSoundCloudUnavailableError,
    isSoundCloudUnavailableTrack,
    markTrackUnavailableInSession,
    showPlaybackErrorOnce,
  ])

  useEffect(() => {
    if (isCardOpen) return
    if (!wantResumeAfterCardCloseRef.current) return
    wantResumeAfterCardCloseRef.current = false
    const a = audioRef.current
    if (!a || !track) return
    if (!a.paused) return
    if (track.access_mode === 'third_party_stream') {
      const sec = a.currentTime
      void rebindThirdPartyStream(
        track,
        a,
        sec,
      ).catch(() => {})
      return
    }
    void requestPlayback(a)
  }, [isCardOpen, requestPlayback, track, rebindThirdPartyStream])

  const playTrack = async (
    newTrack: Track,
    optsOrUrl?:
      | string
      | { url?: string; contextTracks?: Track[]; preserveQueue?: boolean },
  ) => {
    const overrideUrl: string | undefined =
      typeof optsOrUrl === 'string'
        ? optsOrUrl
        : optsOrUrl?.url
    const contextTracks: Track[] | undefined =
      typeof optsOrUrl === 'object' && optsOrUrl !== null
        ? optsOrUrl.contextTracks
        : undefined
    const preserveQueue =
      typeof optsOrUrl === 'object' &&
      optsOrUrl !== null &&
      optsOrUrl.preserveQueue === true
    const isInjectedAdvance = playTrackSlideInjectRef.current !== null
    const hasContextTracks =
      contextTracks !== undefined && contextTracks.length > 0
    if (!isInjectedAdvance && !preserveQueue) {
      prefetchCacheRef.current = null
      if (!hasContextTracks) {
        manualQueueRef.current = []
        setQueue([])
        radioSessionTimelineRef.current = []
        setRadioSessionTimeline([])
        radioModeRef.current = false
        radioSeedTrackIdRef.current = null
        setRadioMode(false)
        setRadioSeedTrackId(null)
        _saveRadioState(false, null)
      }
    }
    if (!radioModeRef.current && !isInjectedAdvance) {
      radioAutoSkipHaltedRef.current = false
      radioAutoSkipsRef.current = 0
      consecutiveAutoSkipsRef.current = 0
    }
    if (hasContextTracks) {
      const idx = contextTracks.findIndex(
        (it) => it.id === newTrack.id,
      )
      const tail =
        idx >= 0
          ? contextTracks.slice(idx + 1)
          : contextTracks.filter(
              (it) => it.id !== newTrack.id,
            )
      manualQueueRef.current = [...tail]
      setQueue([...tail])
      radioModeRef.current = false
      radioSeedTrackIdRef.current = null
      setRadioMode(false)
      setRadioSeedTrackId(null)
    }
    const session = ++playSessionRef.current
    const bail = () => session !== playSessionRef.current
    const audio = audioRef.current
    if (!audio) {
      playTrackSlideInjectRef.current = null
      return
    }
    // Preventive skip: backend flagged the track as inactive. Bail out
    // before touching audio.src so we don't trigger a buffer→error
    // round-trip just to find out it's broken.
    if (newTrack.is_active === false) {
      playTrackSlideInjectRef.current = null
      lastTrackIdRef.current = newTrack.id
      void skipUnavailableTrack(newTrack.id, {
        errorCode: 'track_inactive',
        errorReason: 'backend_flagged_track_inactive',
      })
      return
    }
    beginMediaSessionSwitchHold(audio, newTrack)
    crossfadeFiredForRef.current = null
    playSwitchStartedAtRef.current = {
      trackId: newTrack.id,
      ts:
        typeof performance !== 'undefined' &&
        typeof performance.now === 'function'
          ? performance.now()
          : Date.now(),
      surface: radioModeRef.current ? 'radio' : 'player',
    }
    // Update the system notification drawer *before* the audio src
    // swap so Android sees a continuous session: same playbackState,
    // already-correct metadata, already-correct duration. Without
    // this the drawer flashes blank between the previous track's
    // pause event and the new track's first play event (the user-
    // reported "drawer disappears on switch"). We also pre-warm the
    // artwork URLs into the browser/SW cache so the bitmap is not
    // fetched lazily *during* setMetadata, which is what causes the
    // "blank tile" frame on some Chromium builds.
    _warmCoverArtwork(newTrack)
    if ('mediaSession' in navigator) {
      try {
        _updateMediaSession(
          newTrack,
          audio,
          () => playNext(),
          () => playPrev(),
        )
        _pushPositionStateForTrack(audio, newTrack)
        // Force ``playing`` even though ``audio.paused`` is still
        // true at this exact moment: the hold timer + onPause guard
        // already keep this state until the new track actually
        // starts playing, so the drawer does not flicker through a
        // ``paused`` state purely as a side effect of swapping src.
        navigator.mediaSession.playbackState = 'playing'
      } catch {
        // mediaSession can be unavailable in older webviews; the
        // player still works without the system drawer, just less
        // pretty.
      }
    }
    let prevForSlide: number | null = null
    setTrack((prev) => {
      prevForSlide = prev?.id ?? null
      if (prev && prev.id !== newTrack.id) {
        const h = historyRef.current
        if (
          h.length === 0 ||
          h[h.length - 1].id !== prev.id
        ) {
          h.push(prev)
          if (h.length > 50) h.shift()
          setHistory([...h])
        }
      }
      return newTrack
    })
    const injected = playTrackSlideInjectRef.current
    playTrackSlideInjectRef.current = null
    if (
      prevForSlide !== null &&
      prevForSlide !== newTrack.id
    ) {
      const dir: 0 | 1 | -1 =
        injected === 1 || injected === -1
          ? injected
          : 0
      setTrackChangeSlide((c) => ({
        bump: c.bump + 1,
        dir,
      }))
    }
    streamExpiresAtRef.current = null
    lastStreamUrlRef.current = null
    lastTrackIdRef.current = newTrack.id
    streamLoadFailedTrackIdRef.current = null
    setHlsError(null)
    void loadEqSettings()
    // Fire-and-forget: kick off the hls.js dynamic import in parallel
    // with the cache lookup / src reset / state updates below. After
    // the first call its promise is memoised, so by the time we hit
    // ``await loadHlsClass()`` further down it is already resolved
    // and adds zero async barrier between assigning the new src and
    // calling play() (the gap that breaks iOS Safari autoplay).
    if (shouldUseInternalHlsPlayback(newTrack)) {
      void loadHlsClass()
    }
    if (bail()) return
    _initAudioCtx()
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }
    playCountSentRef.current = false
    listenSignalSentRef.current = false
    // Capture the volume the user actually wants to hear before we
    // touch ``audio.volume`` for the cross-track fade. Falls back to
    // the React-state ``volume`` if the audio element is currently
    // muted to zero by an in-progress fade from the *previous*
    // switch.
    const targetVolume =
      audio.volume > 0 ? audio.volume : volume
    // Soft fade-out + explicit pause guarantees the previous source
    // cannot keep emitting audio while the new src is loading. This
    // is the fix for the user-reported "tracks overlap" symptom: on
    // some Chromium-Android builds setting ``audio.src = newUrl``
    // implicitly schedules a pause but the buffer release is async,
    // so for ~100-300 ms both the tail of the old track and the
    // first frames of the new one play simultaneously. We avoid the
    // legacy ``src=''`` + ``load()`` reset trio (those break iOS
    // Safari's user-gesture chain), but a plain ``pause()`` is safe
    // on every platform and is exactly the missing barrier.
    if (!audio.paused && audio.volume > 0) {
      try {
        await _tweenVolume(audio, 0, TRACK_FADE_OUT_MS)
      } catch {
        /* tweening is best-effort; never block the switch */
      }
    }
    try {
      audio.pause()
    } catch {
      /* ignore */
    }
    // Drop volume to silence so the new track fades *in* from zero
    // instead of clipping in at full volume the moment ``canplay``
    // fires. The fade-in is kicked off below after the audio is
    // actually ready to play.
    try {
      audio.volume = 0
    } catch {
      /* ignore */
    }
    setIsPlaying(false)
    setIsPlayingFromCache(false)
    setCurrentTime(0)
    setDuration(newTrack.duration_seconds ?? 0)
    _saveState(newTrack, 0)
    if (audio) {
      audio.playbackRate = playbackRate
      _applyPitchPreservation(audio)
    }
    const scheduleFadeIn = () => {
      if (bail()) return
      const a = audioRef.current
      if (!a) return
      if (lastTrackIdRef.current !== newTrack.id) return
      const runFade = () => {
        if (lastTrackIdRef.current !== newTrack.id) return
        try {
          a.volume = 0
        } catch {
          /* ignore */
        }
        void _tweenVolume(a, targetVolume, TRACK_FADE_IN_MS)
      }
      if (a.readyState >= 2 || !a.paused) {
        runFade()
        return
      }
      const onReady = () => {
        a.removeEventListener('canplay', onReady)
        a.removeEventListener('playing', onReady)
        if (timeoutId !== null) {
          window.clearTimeout(timeoutId)
        }
        runFade()
      }
      a.addEventListener('canplay', onReady, { once: true })
      a.addEventListener('playing', onReady, { once: true })
      const timeoutId = window.setTimeout(() => {
        a.removeEventListener('canplay', onReady)
        a.removeEventListener('playing', onReady)
        // Even if the load stalls beyond the cap we must restore the
        // user-visible volume; otherwise an autoplay block would
        // leave the slider at 0 and the user would think the player
        // muted itself.
        try {
          a.volume = targetVolume
        } catch {
          /* ignore */
        }
      }, 5000)
    }

    if (
      newTrack.access_mode === 'official_embed' ||
      newTrack.access_mode === 'external_link'
    ) {
      const message = i18n.t('redesign.playerErrors.playback')
      streamLoadFailedTrackIdRef.current = newTrack.id
      showPlaybackErrorOnce(newTrack.id, message)
      await skipUnavailableTrack(newTrack.id, {
        errorReason: newTrack.access_mode,
      })
      return
    }

    const resumeRaw = newTrack.resume_position_seconds
    const totalRaw = newTrack.duration_seconds
    if (
      typeof resumeRaw === 'number' &&
      resumeRaw > 5 &&
      (typeof totalRaw !== 'number' ||
        resumeRaw < totalRaw - 10)
    ) {
      const onMeta = () => {
        try {
          const a = audioRef.current
          if (!a) return
          if (lastTrackIdRef.current !== newTrack.id) return
          const target = Math.min(
            resumeRaw,
            Math.max(0, (a.duration || resumeRaw + 1) - 1),
          )
          if (target > 1 && Number.isFinite(target)) {
            a.currentTime = target
            listenStartTimeRef.current = target
          }
        } catch {
          // currentTime can throw on some readyStates; skip
        }
      }
      audio.addEventListener('loadedmetadata', onMeta, {
        once: true,
      })
    }

    try {
      audio.crossOrigin = 'anonymous'

      // Sync gate: skip the IDB / Cache API lookup entirely when
      // we know synchronously that the track was never pinned for
      // offline. ``isCachedSync`` reads an in-memory Set populated
      // by ensureCachedIdsLoaded(), so on the radio hot path we
      // shave another async barrier off the gap between the user
      // gesture and audio.src=newUrl.
      const cachedUrl = isCachedSync(newTrack.id)
        ? await getCachedAudioUrl(newTrack.id)
        : null
      if (bail()) return
      if (cachedUrl) {
        setIsPlayingFromCache(true)
        recordPlaybackSourceTelemetry(
          audio,
          newTrack.id,
          'cached',
        )
        await startDirectPlayback(audio, cachedUrl)
        if (bail()) return
        void markCachePlayed(newTrack.id).catch(() => {})
        finishMediaSessionSwitch(newTrack, audio)
        scheduleFadeIn()
        return
      }

      if (
        typeof navigator !== 'undefined' &&
        navigator.onLine === false
      ) {
        showIsland({
          kind: 'toast',
          title: i18n.t('offline.onlyCachedHint', {
            defaultValue:
              'Без сети доступны только сохранённые треки',
          }),
          durationMs: 3500,
        })
      }

      if (newTrack.access_mode === 'third_party_stream') {
        const ovr = getThirdPartyStreamOverride(
          newTrack.id,
        )
        // Hot path: a pre-resolved stream URL for this exact track
        // is already in flight (or done) from the prefetch effect.
        // Skip the ``await api.getStream`` round-trip so the audio
        // src is assigned in the same tick as the user gesture --
        // this is the difference between "next track plays now" and
        // "next track sits in paused state for ~1.5 s while we wait
        // for getStream to come back".
        const prefetched =
          ovr === null
            ? _consumePrefetchedStream(
                prefetchedStreamsRef,
                newTrack.id,
              )
            : null
        const stream: StreamResponse =
          ovr !== null
            ? {
                track_id: newTrack.id,
                url: ovr,
                stream_type: inferStreamTypeFromUrl(
                  ovr,
                ),
                expires_in: 86_400,
              }
            : prefetched
              ? prefetched
              : await api.getStream(newTrack.id)
        if (bail()) return
        lastStreamUrlRef.current = stream.url
        streamExpiresAtRef.current = stream.expires_in
          ? Date.now() + stream.expires_in * 1000
          : null
        recordPlaybackSourceTelemetry(
          audio,
          newTrack.id,
          'third_party_stream',
        )
        const HlsMod = await loadHlsClass()
        if (
          stream.stream_type === 'hls' &&
          HlsMod.isSupported()
        ) {
          await startHlsPlayback(
            audio,
            stream.url,
            undefined,
            true,
            newTrack.id,
          )
        } else {
          await startDirectPlayback(
            audio,
            stream.url,
          )
        }
        if (bail()) return

        finishMediaSessionSwitch(newTrack, audio)
        scheduleFadeIn()
        return
      }

      if (!newTrack.is_public) {
        const prefetchedPrivate = _consumePrefetchedStream(
          prefetchedStreamsRef,
          newTrack.id,
        )
        const stream: StreamResponse = prefetchedPrivate
          ? prefetchedPrivate
          : await api.getStream(newTrack.id)
        if (bail()) return
        lastStreamUrlRef.current = stream.url
        streamExpiresAtRef.current = stream.expires_in
          ? Date.now() + stream.expires_in * 1000
          : null
        recordPlaybackSourceTelemetry(
          audio,
          newTrack.id,
          'progressive',
        )
        await startDirectPlayback(audio, stream.url)
        if (bail()) return
        finishMediaSessionSwitch(newTrack, audio)
        scheduleFadeIn()
        return
      }

      const fallback =
        overrideUrl ||
        trackProgressiveAudioUrl(newTrack.id)

      const useHls = shouldUseInternalHlsPlayback(newTrack)
      recordPlaybackSourceTelemetry(
        audio,
        newTrack.id,
        useHls ? 'hls' : 'progressive',
      )
      if (useHls) {
        const hlsUrl = `/api/v1/tracks/${newTrack.id}/hls/master.m3u8`
        // Fast path: a preloaded Hls instance already attached to a
        // detached <audio> sink for this trackId. Reattach to the
        // real audio element synchronously so play() runs in the
        // same tick as the user-gesture / autoplay continuation
        // (no await loadHlsClass() barrier here -- otherwise iOS
        // Safari forbids the next play() and we silent-fail in
        // safePlay, which is what surfaces as "track is paused
        // after switch, user has to press play".
        const preloaded =
          preloadHlsRef.current &&
          preloadHlsTrackIdRef.current === newTrack.id
            ? preloadHlsRef.current
            : null
        if (preloaded) {
          try {
            preloaded.detachMedia()
            preloaded.attachMedia(audio)
            // Keep the volume at 0 here -- ``scheduleFadeIn`` below
            // takes the element from silence to ``targetVolume``
            // once the audio is actually playing. Setting full
            // volume right after attach would clip the start of
            // the new track on top of the (already paused) tail of
            // the previous one.
            audio.volume = 0
            const pinPref = getHlsQualityPreference()
            if (pinPref !== 'auto') {
              const want = pinPref === 'hi' ? 'hi' : 'lo'
              const levels = preloaded.levels as
                | ReadonlyArray<{ url?: readonly string[] }>
                | undefined
              if (levels && levels.length > 0) {
                for (let i = 0; i < levels.length; i += 1) {
                  const urls = levels[i]?.url ?? []
                  if (urls.some((u) => u.includes(`/${want}/`))) {
                    try {
                      preloaded.currentLevel = i
                    } catch {
                      /* best-effort */
                    }
                    break
                  }
                }
              }
            }
            void requestPlayback(audio)
            hlsRef.current = preloaded
            preloadHlsRef.current = null
            preloadHlsTrackIdRef.current = null
          } catch {
            await startHlsPlayback(
              audio,
              hlsUrl,
              fallback,
              true,
              newTrack.id,
            )
          }
        } else {
          const HlsMod = await loadHlsClass()
          if (HlsMod.isSupported()) {
            await startHlsPlayback(
              audio,
              hlsUrl,
              fallback,
              true,
              newTrack.id,
            )
          } else {
            await startDirectPlayback(
              audio,
              fallback,
            )
          }
        }
      } else {
        await startDirectPlayback(
          audio,
          fallback,
        )
      }
      if (bail()) return

      finishMediaSessionSwitch(newTrack, audio)
      scheduleFadeIn()

      // Detect autoplay block on programmatic advance (radio /
      // ended / queue auto-advance): play() returned without
      // throwing but the audio stayed paused because the browser
      // refused autoplay. Surface a toast prompting the user to
      // press play, instead of letting the player sit silently
      // paused with no feedback.
      if (isInjectedAdvance) {
        window.setTimeout(() => {
          const a = audioRef.current
          if (!a) return
          if (lastTrackIdRef.current !== newTrack.id) return
          if (!a.paused) return
          if (a.error != null) return
          if (streamLoadFailedTrackIdRef.current === newTrack.id) {
            return
          }
          showIsland({
            kind: 'toast',
            title: i18n.t('redesign.playerErrors.tapToPlay', {
              defaultValue:
                'Нажмите Play, чтобы продолжить воспроизведение',
            }),
            durationMs: 3500,
          })
        }, 1500)
      }
    } catch (e) {
      if (isBenignPlayError(e)) return
      console.error('playTrack error', e)
      streamLoadFailedTrackIdRef.current =
        newTrack.id
      const message = getApiErrorMessage(
        e,
        i18n.t('redesign.playerErrors.playback'),
      )
      const telemetry = getApiErrorTelemetry(e)
      const scUnavailable =
        isSoundCloudUnavailableTrack(newTrack) &&
        isSoundCloudUnavailableError(message)
      if (!scUnavailable) {
        showPlaybackErrorOnce(newTrack.id, message)
      }
      await skipUnavailableTrack(
        newTrack.id,
        telemetry,
      )
    }
  }

  const clearPendingCommentFocus = useCallback(() => {
    setPendingCommentFocus(null)
  }, [])

  const startRadio = async (seedTrack: Track) => {
    radioAutoSkipHaltedRef.current = false
    radioAutoSkipsRef.current = 0
    consecutiveAutoSkipsRef.current = 0
    lastUnavailableFailureRef.current = {}
    radioSessionTimelineRef.current = []
    setRadioSessionTimeline([])
    radioModeRef.current = true
    radioSeedTrackIdRef.current = seedTrack.id
    radioPlayedIdsRef.current = new Set([seedTrack.id])
    setRadioMode(true)
    setRadioSeedTrackId(seedTrack.id)
    _saveRadioState(true, seedTrack.id)
    try {
      const result = await api.getRadio(
        seedTrack.id,
        RADIO_BATCH_SIZE,
      )
      const newTracks = result.tracks.filter(
        (t) => !radioPlayedIdsRef.current.has(t.id),
      )
      for (const t of newTracks) {
        radioPlayedIdsRef.current.add(t.id)
      }
      manualQueueRef.current = [...newTracks]
      setQueue([...newTracks])
      try {
        void getPrefetchManager().enqueue(newTracks, {
          context: 'radio',
          replaceContext: true,
        })
      } catch {
        /* ignore prefetch errors */
      }
    } catch {
      /* best-effort */
    }
    await playTrack(seedTrack, { preserveQueue: true })
  }

  const stopRadio = () => {
    radioAutoSkipHaltedRef.current = false
    radioAutoSkipsRef.current = 0
    consecutiveAutoSkipsRef.current = 0
    radioSessionTimelineRef.current = []
    setRadioSessionTimeline([])
    radioModeRef.current = false
    radioSeedTrackIdRef.current = null
    setRadioMode(false)
    setRadioSeedTrackId(null)
    _saveRadioState(false, null)
    manualQueueRef.current = []
    setQueue([])
    const a = audioRef.current
    if (a && !a.paused) {
      try {
        a.pause()
      } catch {
        /* ignore */
      }
    }
    setIsPlaying(false)
  }

  const playNext = async (
    opts?: {
      afterNaturalEnd?: boolean
      bypassInFlightGuard?: boolean
    },
  ): Promise<boolean> => {
    if (radioAutoSkipHaltedRef.current) {
      return false
    }
    const sessionTrackId =
      lastTrackIdRef.current ?? track?.id ?? null
    if (
      sessionTrackId == null &&
      manualQueueRef.current.length === 0 &&
      !radioModeRef.current
    ) {
      return false
    }
    const bypassInFlight = opts?.bypassInFlightGuard === true
    if (playNextInFlightRef.current && !bypassInFlight) {
      return false
    }
    const tookPlayNextLock = !playNextInFlightRef.current
    if (tookPlayNextLock) {
      playNextInFlightRef.current = true
    }
    // Always declare this advance as forward-injected so the inner
    // playTrack call doesn't treat it as a fresh user action and
    // wipe the radio session / manual queue. Without this guard
    // skipUnavailableTrack -> playNext (bypassInFlightGuard) running
    // re-entrantly while another playNext owns the lock would land
    // in playTrack with isInjectedAdvance=false and reset radio mode.
    if (playTrackSlideInjectRef.current === null) {
      playTrackSlideInjectRef.current = 1
    }
    const advance = async (next: Track): Promise<boolean> => {
      if (radioAutoSkipHaltedRef.current) return false
      if (playTrackSlideInjectRef.current === null) {
        playTrackSlideInjectRef.current = 1
      }
      await playTrack(next, { preserveQueue: true })
      return true
    }
    try {
    if (radioAutoSkipHaltedRef.current) {
      return false
    }
    const isOffline =
      typeof navigator !== 'undefined' &&
      navigator.onLine === false
    if (isOffline) {
      // 1. Honour the user's explicit queue first, but only
      //    pick tracks that are also cached locally.
      if (manualQueueRef.current.length > 0) {
        const { isCached } = await import(
          '@/lib/offlineCache'
        )
        for (
          let i = 0;
          i < manualQueueRef.current.length;
          i += 1
        ) {
          const item = manualQueueRef.current[i]
          if (
            !item ||
            unavailableTrackIdsRef.current.has(item.id)
          )
            continue
          if (await isCached(item.id)) {
            manualQueueRef.current.splice(i, 1)
            setQueue([...manualQueueRef.current])
            return await advance(item)
          }
        }
      }
      // 2. Fall back to any cached track in IDB.
      const ok = await _fallbackToCachedTrack(
        sessionTrackId ?? track?.id ?? 0,
      )
      if (ok) return true
      // 3. Nothing cached — give up; do NOT attempt radio /
      //    prefetch / adjacent (all rely on the network).
      return false
    }
    try {
      if (manualQueueRef.current.length > 0) {
        const nextIdx = manualQueueRef.current.findIndex(
          (item) => !unavailableTrackIdsRef.current.has(item.id),
        )
        if (nextIdx < 0) {
          manualQueueRef.current = []
          setQueue([])
          return false
        }
        const [next] = manualQueueRef.current.splice(nextIdx, 1)
        if (!next) {
          return false
        }
        setQueue([...manualQueueRef.current])
        // Pro-active radio top-up: if the queue is about to run dry
        // we kick off a background ``getRadio`` so the *next* tap
        // doesn't have to wait for an in-band refill on the hot
        // path. Especially important when the screen is locked,
        // because Android will throttle/abort fetches issued during
        // an in-flight track switch but is much more lenient about
        // ones started while playback is steady.
        if (
          radioModeRef.current &&
          radioSeedTrackIdRef.current &&
          manualQueueRef.current.length <= RADIO_REFILL_THRESHOLD
        ) {
          const seedId = radioSeedTrackIdRef.current
          const excludeIds = Array.from(
            radioPlayedIdsRef.current,
          ).slice(-60)
          api
            .getRadio(seedId, RADIO_BATCH_SIZE, excludeIds)
            .then((result) => {
              if (!radioModeRef.current) return
              if (radioSeedTrackIdRef.current !== seedId) return
              const fresh = result.tracks.filter(
                (t) =>
                  !radioPlayedIdsRef.current.has(t.id) &&
                  !unavailableTrackIdsRef.current.has(t.id) &&
                  !manualQueueRef.current.some(
                    (existing) => existing.id === t.id,
                  ),
              )
              if (fresh.length === 0) return
              for (const t of fresh) {
                radioPlayedIdsRef.current.add(t.id)
              }
              if (radioPlayedIdsRef.current.size > 80) {
                const arr = Array.from(radioPlayedIdsRef.current)
                radioPlayedIdsRef.current = new Set(arr.slice(-80))
              }
              manualQueueRef.current = [
                ...manualQueueRef.current,
                ...fresh,
              ]
              setQueue([...manualQueueRef.current])
              try {
                void getPrefetchManager().enqueue(fresh, {
                  context: 'radio',
                })
              } catch {
                /* ignore */
              }
            })
            .catch(() => {
              /* best-effort top-up; the in-band refill in the empty-
               * queue branch below will still cover the worst case. */
            })
        }
        return await advance(next)
      }

      if (radioModeRef.current && radioSeedTrackIdRef.current) {
        const seedId = radioSeedTrackIdRef.current
        const excludeIds = Array.from(
          radioPlayedIdsRef.current,
        ).slice(-60)
        try {
          const result = await api.getRadio(
            seedId,
            RADIO_BATCH_SIZE,
            excludeIds,
          )
          const newTracks = result.tracks.filter(
            (t) =>
              !radioPlayedIdsRef.current.has(t.id) &&
              !unavailableTrackIdsRef.current.has(t.id),
          )
          if (newTracks.length > 0) {
            const next = newTracks[0]
            for (const t of newTracks) {
              radioPlayedIdsRef.current.add(t.id)
            }
            if (radioPlayedIdsRef.current.size > 80) {
              const arr = Array.from(radioPlayedIdsRef.current)
              radioPlayedIdsRef.current = new Set(arr.slice(-80))
            }
            manualQueueRef.current = newTracks.slice(1)
            setQueue([...manualQueueRef.current])
            return await advance(next)
          }
        } catch {
          /* continue to adjacent fallback */
        }
      }

      const cache = prefetchCacheRef.current
      const allowPrefetchAdvance =
        !opts?.afterNaturalEnd || radioModeRef.current
      if (
        allowPrefetchAdvance &&
        cache &&
        sessionTrackId != null &&
        cache.forTrackId === sessionTrackId &&
        cache.tracks.length > 0
      ) {
        const availableCacheTracks = cache.tracks.filter(
          (item) => !unavailableTrackIdsRef.current.has(item.id),
        )
        if (availableCacheTracks.length === 0) {
          prefetchCacheRef.current = null
        } else {
        let next: Track
        if (shuffleOnRef.current && availableCacheTracks.length > 1) {
          const idx = Math.floor(Math.random() * availableCacheTracks.length)
          next = availableCacheTracks[idx]
          prefetchCacheRef.current = {
            forTrackId: next.id,
            tracks: availableCacheTracks.filter(
              (_, i) => i !== idx,
            ),
          }
        } else {
          next = availableCacheTracks[0]
          prefetchCacheRef.current = {
            forTrackId: next.id,
            tracks: availableCacheTracks.slice(1),
          }
        }
        return await advance(next)
        }
      }
      if (radioAutoSkipHaltedRef.current) return false
      return await _fallbackToCachedTrack(
        sessionTrackId ?? track?.id ?? 0,
      )
    } catch {
      if (radioAutoSkipHaltedRef.current) return false
      return await _fallbackToCachedTrack(
        sessionTrackId ?? track?.id ?? 0,
      )
    }
    } finally {
      if (tookPlayNextLock) {
        playTrackSlideInjectRef.current = null
        playNextInFlightRef.current = false
      }
    }
  }

  const _fallbackToCachedTrack = async (
    excludeId: number,
  ): Promise<boolean> => {
    const isOffline =
      typeof navigator !== 'undefined' &&
      navigator.onLine === false
    if (!isOffline) return false
    try {
      const { getCachedTracks } = await import(
        '@/lib/offlineCache'
      )
      const cached = await getCachedTracks()
      const next = cached.find(
        (rec) =>
          rec.trackId !== excludeId &&
          !unavailableTrackIdsRef.current.has(rec.trackId) &&
          rec.track !== undefined,
      )
      if (!next || !next.track) return false
      await playTrack(next.track, { preserveQueue: true })
      return true
    } catch {
      return false
    }
  }

  useEffect(() => {
    if (!track) return
    let cancelled = false

    try {
      getPrefetchManager().markPlaybackStart(track.id)
    } catch {
      /* ignore telemetry failures */
    }

    const teardownPreloadHls = () => {
      if (preloadHlsRef.current) {
        try {
          preloadHlsRef.current.destroy()
        } catch {
          /* ignore */
        }
        preloadHlsRef.current = null
      }
      preloadHlsTrackIdRef.current = null
    }

    const teardownSwCachePrefetch = () => {
      if (swCachePrefetchAbortRef.current) {
        try {
          swCachePrefetchAbortRef.current.abort()
        } catch {
          /* ignore */
        }
        swCachePrefetchAbortRef.current = null
      }
      swCachePrefetchTrackIdRef.current = null
      if (swCachePrefetchSecondAbortRef.current) {
        try {
          swCachePrefetchSecondAbortRef.current.abort()
        } catch {
          /* ignore */
        }
        swCachePrefetchSecondAbortRef.current = null
      }
    }

    const preloadFirst = (tracks: Track[]) => {
      if (cancelled || !tracks.length) return
      const next = tracks[0]
      if (prefetchAudioRef.current) {
        prefetchAudioRef.current.src = ''
        prefetchAudioRef.current = null
      }
      teardownPreloadHls()
      teardownSwCachePrefetch()
      // Pre-warm the system notification artwork for the *next*
      // probable track. The browser stuffs the bitmap into the SW
      // cache (covers-cache route), so the actual setMetadata call
      // during playTrack does not have to fetch it -- avoids the
      // "blank tile flicker" frame on the Android drawer.
      _warmCoverArtwork(next)
      // Pre-resolve stream URLs for the next ``PREFETCH_STREAM_AHEAD``
      // tracks (only those that need a backend round-trip per play:
      // third_party_stream / private). Tracks that don't need a
      // resolve are skipped silently, so this is "up to N", not
      // "exactly N". Old entries in the cache that we are no longer
      // looking at get evicted to keep the map bounded.
      const upcomingIds = new Set<number>()
      for (
        let i = 0;
        i < Math.min(PREFETCH_STREAM_AHEAD, tracks.length);
        i += 1
      ) {
        upcomingIds.add(tracks[i].id)
      }
      for (const cachedId of Array.from(prefetchedStreamsRef.current.keys())) {
        if (!upcomingIds.has(cachedId)) {
          prefetchedStreamsRef.current.delete(cachedId)
        }
      }
      const needsStreamPrefetch = (t: Track) =>
        t.access_mode === 'third_party_stream' ||
        (t.is_public === false &&
          t.access_mode !== 'official_embed' &&
          t.access_mode !== 'external_link')
      for (
        let i = 0;
        i < Math.min(PREFETCH_STREAM_AHEAD, tracks.length);
        i += 1
      ) {
        const candidate = tracks[i]
        if (!needsStreamPrefetch(candidate)) continue
        const cached = prefetchedStreamsRef.current.get(candidate.id)
        const fresh =
          cached !== undefined &&
          Date.now() - cached.resolvedAt < PREFETCHED_STREAM_TTL_MS &&
          (cached.expiresAt === null ||
            cached.expiresAt > Date.now() + 5_000)
        if (fresh) continue
        const prefetchTrackId = candidate.id
        api
          .getStream(prefetchTrackId)
          .then((stream) => {
            if (cancelled) return
            if (lastTrackIdRef.current !== track.id) return
            prefetchedStreamsRef.current.set(prefetchTrackId, {
              trackId: prefetchTrackId,
              url: stream.url,
              streamType: stream.stream_type,
              expiresAt: stream.expires_in
                ? Date.now() + stream.expires_in * 1000
                : null,
              resolvedAt: Date.now(),
            })
          })
          .catch(() => {
            /* best-effort prefetch: if the resolve fails, playTrack
             * will fall through to its own ``api.getStream`` call
             * the regular way. */
          })
      }
      if (
        next.access_mode === 'official_embed' ||
        next.access_mode === 'external_link'
      ) {
        return
      }

      // Native disk-cache prewarm: a hidden <Audio preload='auto'>
      // gets the browser to issue Range probes and pin them to its
      // own HTTP cache. This helps Chrome on desktop but on mobile
      // browsers the disk cache eviction is so aggressive that we
      // cannot rely on it for radio mode -- we also need the SW
      // cache to be populated (see below).
      const pa = new Audio()
      pa.preload = 'auto'
      pa.src = trackProgressiveAudioUrl(next.id)
      _applyPitchPreservation(pa)
      prefetchAudioRef.current = pa

      // Real SW Cache prefetch: full-body GET (status 200) so
      // workbox's CacheFirst route writes the entire file into
      // ``progressive-audio-cache``. The next track switch then
      // hits the SW cache instead of the network and starts
      // playing in <200ms instead of waiting for the OS network
      // stack + CDN to ramp up. This is the difference between
      // "track pauses on switch, user has to press play, waits 5s
      // for buffering" and "next track plays seamlessly".
      // Skipped for HLS-eligible tracks (they have their own
      // segment-level prefetch via preloadHlsRef and shouldn't
      // burn data plan on a duplicate progressive download).
      if (!shouldUseInternalHlsPlayback(next)) {
        const ctrl = new AbortController()
        swCachePrefetchAbortRef.current = ctrl
        swCachePrefetchTrackIdRef.current = next.id
        void prefetchProgressiveBodyForCache(next.id, {
          signal: ctrl.signal,
        }).finally(() => {
          if (
            swCachePrefetchTrackIdRef.current === next.id &&
            swCachePrefetchAbortRef.current === ctrl
          ) {
            swCachePrefetchAbortRef.current = null
            swCachePrefetchTrackIdRef.current = null
          }
        })
      }

      // In radio mode prefetch the second-next track into SW cache
      // immediately (fire-and-forget, low network priority). This
      // ensures that when the current track ends and we advance to
      // tracks[0], tracks[1] is already warm and ready to go.
      if (radioModeRef.current && tracks.length > 1) {
        const second = tracks[1]
        if (
          second &&
          second.access_mode !== 'official_embed' &&
          second.access_mode !== 'external_link' &&
          second.access_mode !== 'third_party_stream' &&
          !shouldUseInternalHlsPlayback(second)
        ) {
          const ctrl2 = new AbortController()
          swCachePrefetchSecondAbortRef.current = ctrl2
          void prefetchProgressiveBodyForCache(second.id, {
            signal: ctrl2.signal,
          }).finally(() => {
            if (
              swCachePrefetchSecondAbortRef.current === ctrl2
            ) {
              swCachePrefetchSecondAbortRef.current = null
            }
          })
        }
      }

      void (async () => {
        if (!shouldUseInternalHlsPlayback(next)) return
        let HlsMod: Awaited<ReturnType<typeof loadHlsClass>>
        try {
          HlsMod = await loadHlsClass()
        } catch {
          return
        }
        if (cancelled) return
        const canHls = HlsMod.isSupported()
        if (!canHls) return

        try {
          const hls = new HlsMod({
            enableWorker: true,
            startLevel: -1,
            testBandwidth: false,
            autoStartLoad: true,
            maxBufferLength: 12,
            startFragPrefetch: true,
            fragLoadingTimeOut: 8000,
            manifestLoadingTimeOut: 5000,
          })
          hls.loadSource(
            `/api/v1/tracks/${next.id}/hls/master.m3u8`,
          )
          const sink = document.createElement('audio')
          sink.muted = true
          sink.preload = 'auto'
          hls.attachMedia(sink)
          preloadHlsRef.current = hls
          preloadHlsTrackIdRef.current = next.id
          hls.on(HlsMod.Events.ERROR, (_e, d) => {
            if (d.fatal) teardownPreloadHls()
          })
        } catch {
          teardownPreloadHls()
        }
      })()
    }

    api.getRadio(track.id, 5)
      .then((res) => {
        if (cancelled || !res.tracks.length)
          throw new Error('empty')
        // Guard: if track changed while request was in-flight, discard stale response.
        // cancelled alone isn't enough — React cleanup runs async after state flush.
        if (lastTrackIdRef.current !== track.id) return
        prefetchCacheRef.current = {
          forTrackId: track.id,
          tracks: res.tracks,
        }
        preloadFirst(res.tracks)
        try {
          void getPrefetchManager().enqueue(res.tracks, {
            context: radioModeRef.current ? 'radio' : 'playback',
            replaceContext: true,
          })
        } catch {
          /* ignore */
        }
      })
      .catch(() => {
        api.getTrackQueue(track.id, 3)
          .then((res) => {
            if (cancelled || lastTrackIdRef.current !== track.id) return
            prefetchCacheRef.current = {
              forTrackId: track.id,
              tracks: res.next_tracks,
            }
            preloadFirst(res.next_tracks)
            try {
              void getPrefetchManager().enqueue(
                res.next_tracks,
                {
                  context: 'queue',
                  replaceContext: true,
                },
              )
            } catch {
              /* ignore */
            }
          })
          .catch(() => {})
      })
    return () => {
      cancelled = true
      if (prefetchAudioRef.current) {
        prefetchAudioRef.current.src = ''
        prefetchAudioRef.current = null
      }
      teardownPreloadHls()
      teardownSwCachePrefetch()
    }
  }, [track?.id])

  useEffect(() => {
    if (!track) return
    if (!radioMode) return
    const timeline = radioSessionTimelineRef.current
    const last = timeline[timeline.length - 1]
    if (last && last.id === track.id) return
    radioSessionTimelineRef.current = [...timeline, track].slice(-30)
    setRadioSessionTimeline([...radioSessionTimelineRef.current])
  }, [track, radioMode])

  const applyRadioTimelineBack = async (): Promise<boolean> => {
    const h = radioSessionTimelineRef.current
    if (h.length < 2) return false
    playNextInFlightRef.current = true
    playTrackSlideInjectRef.current = -1
    try {
      const nextTimeline = h.slice(0, -1)
      radioSessionTimelineRef.current = nextTimeline
      setRadioSessionTimeline([...nextTimeline])
      const prevT = nextTimeline[nextTimeline.length - 1]
      if (!prevT) return false
      await playTrack(prevT, { preserveQueue: true })
      return true
    } finally {
      playTrackSlideInjectRef.current = null
      playNextInFlightRef.current = false
    }
  }

  const playRadioPrevious = async (): Promise<boolean> => {
    if (!radioModeRef.current) return false
    if (playNextInFlightRef.current) return false
    return applyRadioTimelineBack()
  }

  const playPrev = async () => {
    if (!track) return
    if (playNextInFlightRef.current) return
    if (radioModeRef.current) {
      const a = audioRef.current
      if (a && a.currentTime > 3) {
        a.currentTime = 0
        return
      }
      await applyRadioTimelineBack()
      return
    }
    const a = audioRef.current
    if (a && a.currentTime > 3) {
      a.currentTime = 0
      return
    }
    playNextInFlightRef.current = true
    playTrackSlideInjectRef.current = -1
    try {
    const prev = historyRef.current.pop()
    if (prev) {
      await playTrack(prev, { preserveQueue: true })
      return
    }
    try {
      const adj = await api.getAdjacentTracks(
        track.id,
      )
      if (adj.prev_id) {
        const t = await api.getTrack(adj.prev_id)
        await playTrack(t, { preserveQueue: true })
      }
    } catch {}
    } finally {
      playTrackSlideInjectRef.current = null
      playNextInFlightRef.current = false
    }
  }

  const togglePlay = () => {
    const a = audioRef.current
    if (!a || !track) return
    void loadEqSettings()
    _initAudioCtx()
    if (a.paused) {
      if (
        streamLoadFailedTrackIdRef.current ===
        track.id
      ) {
        void playTrack(track, { preserveQueue: true })
        return
      }
      void requestPlayback(a, {
        onNotAllowed: () =>
          showIsland({
            kind: 'error',
            title: i18n.t('redesign.playerErrors.blockedByBrowser'),
            durationMs: 4000,
          }),
      })
    } else a.pause()
  }

  const flushPlayerTimeUi = useCallback(
    () => {
      const a = audioRef.current
      if (!a) return
      playerTimeUiLastRef.current = performance.now()
      setCurrentTime(a.currentTime)
      _updatePositionState(a)
    },
    [],
  )

  const getPreciseTime = useCallback(
    () => audioRef.current?.currentTime ?? currentTimeRef.current,
    [],
  )

  const _applySeek = useCallback(
    (a: HTMLAudioElement, target: number) => {
      const clamped = Math.max(
        0,
        Math.min(a.duration || target, target),
      )
      // HLS-specific: tell hls.js to abort the in-flight fragment and
      // jump to the new position. Without this, a long-distance seek
      // on a still-buffering segment makes the engine wait for the
      // current fetch to complete before starting the new one — which
      // surfaces to the user as a multi-second freeze on scrub.
      const hls = hlsRef.current
      if (hls) {
        try {
          hls.stopLoad()
          hls.startLoad(clamped)
        } catch {
          /* hls.js may not be ready yet; native seek still works */
        }
      }
      // Prefer ``fastSeek`` when available: keyframe-aligned seeks are
      // ~10x faster than precise seeks because the decoder does not
      // need to reconstruct the exact PTS, and music never visibly
      // suffers from rounding to the nearest GOP boundary.
      const fastSeek = (
        a as HTMLAudioElement & {
          fastSeek?: (time: number) => void
        }
      ).fastSeek
      if (typeof fastSeek === 'function') {
        try {
          fastSeek.call(a, clamped)
        } catch {
          a.currentTime = clamped
        }
      } else {
        a.currentTime = clamped
      }
    },
    [],
  )

  const seek = useCallback(
    (pct: number) => {
      const a = audioRef.current
      if (!a || !a.duration) return
      _applySeek(a, (pct / 100) * a.duration)
      flushPlayerTimeUi()
    },
    [_applySeek, flushPlayerTimeUi],
  )

  const stop = () => {
    const a = audioRef.current
    if (a) a.pause()
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }
    streamLoadFailedTrackIdRef.current = null
    prefetchedStreamsRef.current.clear()
    _releaseWakeLock()
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = null
      navigator.mediaSession.playbackState = 'none'
    }
    setTrack(null)
    lastTrackIdRef.current = null
    setTrackChangeSlide({ bump: 0, dir: 0 })
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
    _clearState()
  }

  const seekToSeconds = useCallback(
    (sec: number) => {
      const a = audioRef.current
      if (!a || !a.duration) return
      _applySeek(a, sec)
      flushPlayerTimeUi()
    },
    [_applySeek, flushPlayerTimeUi],
  )

  const skipForward = useCallback(
    (s = 15) => {
      const a = audioRef.current
      if (!a) return
      _applySeek(a, (a.currentTime || 0) + s)
      flushPlayerTimeUi()
    },
    [_applySeek, flushPlayerTimeUi],
  )

  const skipBackward = useCallback(
    (s = 15) => {
      const a = audioRef.current
      if (!a) return
      _applySeek(a, (a.currentTime || 0) - s)
      flushPlayerTimeUi()
    },
    [_applySeek, flushPlayerTimeUi],
  )

  const setPlaybackRate = useCallback(
    (rate: number) => {
      const r = Math.max(0.25, Math.min(2, rate))
      setPlaybackRateState(r)
      const a = audioRef.current
      if (a) {
        a.playbackRate = r
        _applyPitchPreservation(a)
        flushPlayerTimeUi()
      }
    },
    [flushPlayerTimeUi],
  )

  const cancelSleepTimer = useCallback(() => {
    sleepDeadlineRef.current = null
    sleepEndOfTrackRef.current = false
    setSleepMode('off')
    setSleepRemainingSec(0)
  }, [])

  const setSleepTimerMinutes = useCallback(
    (minutes: number) => {
      const safeMinutes = Math.max(1, Math.floor(minutes))
      sleepEndOfTrackRef.current = false
      sleepDeadlineRef.current =
        Date.now() + safeMinutes * 60_000
      setSleepMode('minutes')
      setSleepRemainingSec(safeMinutes * 60)
    },
    [],
  )

  const setSleepTimerEndOfTrack = useCallback(() => {
    sleepDeadlineRef.current = null
    sleepEndOfTrackRef.current = true
    setSleepMode('end-of-track')
    setSleepRemainingSec(0)
  }, [])

  useEffect(() => {
    if (sleepMode !== 'minutes') return
    const tick = () => {
      const dl = sleepDeadlineRef.current
      if (dl == null) return
      const remainingMs = dl - Date.now()
      if (remainingMs <= 0) {
        const a = audioRef.current
        if (a && !a.paused) a.pause()
        sleepDeadlineRef.current = null
        sleepEndOfTrackRef.current = false
        setSleepMode('off')
        setSleepRemainingSec(0)
        return
      }
      setSleepRemainingSec(Math.ceil(remainingMs / 1000))
    }
    tick()
    const interval = window.setInterval(tick, 1000)
    return () => window.clearInterval(interval)
  }, [sleepMode])

  const addToQueue = useCallback((t: Track) => {
    manualQueueRef.current = [
      ...manualQueueRef.current,
      t,
    ]
    setQueue([...manualQueueRef.current])
  }, [])

  const removeFromQueue = useCallback(
    (idx: number) => {
      manualQueueRef.current =
        manualQueueRef.current.filter(
          (_, i) => i !== idx,
        )
      setQueue([...manualQueueRef.current])
    },
    [],
  )

  const clearQueue = useCallback(() => {
    manualQueueRef.current = []
    setQueue([])
  }, [])

  const reorderQueue = useCallback(
    (from: number, to: number) => {
      const arr = [...manualQueueRef.current]
      if (
        from < 0 ||
        from >= arr.length ||
        to < 0 ||
        to >= arr.length
      )
        return
      const [item] = arr.splice(from, 1)
      arr.splice(to, 0, item)
      manualQueueRef.current = arr
      setQueue(arr)
    },
    [],
  )

  const setAbA = useCallback((sec?: number) => {
    const a = audioRef.current
    const value =
      sec ?? (a ? a.currentTime : 0)
    setAbLoop((prev) => {
      const next = { a: value, b: prev.b }
      abLoopRef.current = next
      return next
    })
  }, [])

  const setAbB = useCallback((sec?: number) => {
    const a = audioRef.current
    const value =
      sec ?? (a ? a.currentTime : 0)
    setAbLoop((prev) => {
      const next = { a: prev.a, b: value }
      abLoopRef.current = next
      return next
    })
  }, [])

  const clearAbLoop = useCallback(() => {
    setAbLoop(() => {
      const next = { a: null, b: null }
      abLoopRef.current = next
      return next
    })
  }, [])

  const getAnalyser = useCallback(
    () => analyserRef.current,
    [],
  )

  const updateTrack = useCallback(
    (updated: Partial<Track> & { id: number }) => {
      setTrack((prev) => {
        if (!prev || prev.id !== updated.id)
          return prev
        const merged = { ...prev, ...updated }
        _saveState(merged, audioRef.current?.currentTime ?? 0)
        return merged
      })
    },
    [],
  )

  const stateValue = useMemo<PlayerStateValue>(
    () => ({ currentTime, duration, isPlaying }),
    [currentTime, duration, isPlaying],
  )

  const playbackValue = useMemo<PlayerPlaybackValue>(
    () => ({ isPlaying, duration }),
    [isPlaying, duration],
  )

  const timeValue = useMemo<PlayerTimeValue>(
    () => ({ currentTime }),
    [currentTime],
  )

  const openComplaint = useCallback(
    () => setIsComplaintOpen(true), [],
  )
  const closeComplaint = useCallback(
    () => setIsComplaintOpen(false), [],
  )
  const openCard = useCallback(() => {
    setIsCardOpen(true)
  }, [])

  const openTrackAtComment = useCallback(
    async (t: Track, commentId: number) => {
      setPendingCommentFocus({
        trackId: t.id,
        commentId,
      })
      await playTrack(t)
      openCard()
    },
    [playTrack, openCard],
  )

  /* closeCard без View Transitions: иначе во время анимации
   * у предка остаётся transform и ломается position:fixed у
   * ArtistView/AuthorView; в ряде браузеров страдает и <audio>. */
  const closeCard = useCallback(() => {
    const a = audioRef.current
    wantResumeAfterCardCloseRef.current = Boolean(
      a && !a.paused,
    )
    setIsCardOpen(false)
  }, [])
  const openLyrics = useCallback(
    () => setIsLyricsOpen(true), [],
  )
  const closeLyrics = useCallback(
    () => setIsLyricsOpen(false), [],
  )
  const openEq = useCallback(
    () => setIsEqOpen(true), [],
  )
  const closeEq = useCallback(
    () => setIsEqOpen(false), [],
  )
  const openQueue = useCallback(
    () => setIsQueueOpen(true), [],
  )
  const closeQueue = useCallback(
    () => setIsQueueOpen(false), [],
  )

  const actionsValue = useMemo<PlayerActionsValue>(
    () => ({
      playTrack, togglePlay, seek, seekToSeconds,
      skipForward, skipBackward, setPlaybackRate,
      getPreciseTime,
      playNext, playPrev, playRadioPrevious, setVolume, stop,
      setEqBand, setEqPreset, toggleEqBypass, resetEq,
      toggleRepeat, toggleShuffle, clearHlsError,
      openComplaint, closeComplaint,
      openCard, closeCard,
      openLyrics, closeLyrics,
      openEq, closeEq,
      openQueue, closeQueue,
      addToQueue, removeFromQueue, clearQueue, reorderQueue,
      setAbA, setAbB, clearAbLoop,
      getAnalyser,
      updateTrack,
      clearPendingCommentFocus,
      openTrackAtComment,
      radioMode,
      radioSeedTrackId,
      startRadio,
      stopRadio,
      sleepMode,
      sleepRemainingSec,
      setSleepTimerMinutes,
      setSleepTimerEndOfTrack,
      cancelSleepTimer,
    }),
    [
      playTrack, togglePlay, seek, seekToSeconds,
      skipForward, skipBackward, setPlaybackRate,
      getPreciseTime,
      playNext, playPrev, playRadioPrevious, setVolume, stop,
      setEqBand, setEqPreset, toggleEqBypass, resetEq,
      toggleRepeat, toggleShuffle, clearHlsError,
      openComplaint, closeComplaint,
      openCard, closeCard,
      openLyrics, closeLyrics,
      openEq, closeEq,
      openQueue, closeQueue,
      addToQueue, removeFromQueue, clearQueue, reorderQueue,
      setAbA, setAbB, clearAbLoop,
      getAnalyser,
      updateTrack,
      clearPendingCommentFocus,
      openTrackAtComment,
      radioMode,
      radioSeedTrackId,
      startRadio,
      stopRadio,
      sleepMode,
      sleepRemainingSec,
      setSleepTimerMinutes,
      setSleepTimerEndOfTrack,
      cancelSleepTimer,
    ],
  )

  const metaValue = useMemo<PlayerMetaValue>(
    () => ({
      track, volume,
      isComplaintOpen, isCardOpen,
      isLyricsOpen, isEqOpen, isQueueOpen,
      eqBands, eqPreset, eqBypassed,
      repeatMode, shuffleOn, hlsError,
      playbackRate, queue, history,
      radioSessionTimeline,
      abLoop,
      pendingCommentFocus,
      isPlayingFromCache,
      trackChangeSlide,
    }),
    [
      track, volume,
      isComplaintOpen, isCardOpen,
      isLyricsOpen, isEqOpen, isQueueOpen,
      eqBands, eqPreset, eqBypassed,
      repeatMode, shuffleOn, hlsError,
      playbackRate, queue, history,
      radioSessionTimeline,
      abLoop,
      pendingCommentFocus,
      isPlayingFromCache,
      trackChangeSlide,
    ],
  )

  const legacyValue = useMemo<PlayerContextValue>(
    () => ({
      ...stateValue,
      ...actionsValue,
      ...metaValue,
    }),
    [stateValue, actionsValue, metaValue],
  )

  return (
    <PlayerContext.Provider value={legacyValue}>
      <PlayerStateCtx.Provider value={stateValue}>
        <PlayerPlaybackCtx.Provider value={playbackValue}>
          <PlayerTimeCtx.Provider value={timeValue}>
            <PlayerActionsCtx.Provider value={actionsValue}>
              <PlayerMetaCtx.Provider value={metaValue}>
                <audio
                  ref={audioRef}
                  // ``auto`` lets the browser start fetching the
                  // first segment / Range request as soon as the
                  // src is assigned, without waiting for a play()
                  // call. On a track switch this trims the gap
                  // between ``audio.src = newUrl`` and ``canplay``
                  // by ~150-400 ms on cold connections and is the
                  // single most impactful knob for "next track
                  // plays now" feel. The user explicitly accepted
                  // the extra mobile data trade-off; we already
                  // stop the previous src as soon as we set the
                  // new one, so there is no double-load overlap.
                  preload="auto"
                  crossOrigin="anonymous"
                />
                {children}
              </PlayerMetaCtx.Provider>
            </PlayerActionsCtx.Provider>
          </PlayerTimeCtx.Provider>
        </PlayerPlaybackCtx.Provider>
      </PlayerStateCtx.Provider>
    </PlayerContext.Provider>
  )
}

export function usePlayer() {
  const ctx = useContext(PlayerContext)
  if (!ctx)
    throw new Error(
      'usePlayer must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerState() {
  const ctx = useContext(PlayerStateCtx)
  if (!ctx)
    throw new Error(
      'usePlayerState must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerPlayback() {
  const ctx = useContext(PlayerPlaybackCtx)
  if (!ctx)
    throw new Error(
      'usePlayerPlayback must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerTime() {
  const ctx = useContext(PlayerTimeCtx)
  if (!ctx)
    throw new Error(
      'usePlayerTime must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerActions() {
  const ctx = useContext(PlayerActionsCtx)
  if (!ctx)
    throw new Error(
      'usePlayerActions must be used within PlayerProvider',
    )
  return ctx
}

export function usePlayerMeta() {
  const ctx = useContext(PlayerMetaCtx)
  if (!ctx)
    throw new Error(
      'usePlayerMeta must be used within PlayerProvider',
    )
  return ctx
}
