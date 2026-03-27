import { useLikes } from '@/store/LikesContext'
import { usePlayer } from '@/store/PlayerContext'

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function PlayerBar() {
  const { track, isPlaying, currentTime, duration, togglePlay, seek, openComplaint } = usePlayer()
  const { isLiked, toggleLike } = useLikes()

  if (!track) return null

  const pct = duration ? (currentTime / duration) * 100 : 0
  const liked = isLiked(track.id)

  const handleLike = async () => {
    await toggleLike(track.id)
  }

  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null

  return (
    <div id="player-bar">
      <div id="pb-seek-wrap">
        <input
          type="range"
          id="pb-seek"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          onChange={(e) => seek(Number(e.target.value))}
        />
      </div>
      <div id="pb-row">
        <div className="pb-cover-img">
          {coverSrc ? (
            <img
              src={coverSrc}
              alt=""
              onError={(e) => {
                const el = e.target as HTMLImageElement
                if (el.parentElement) el.parentElement.textContent = '🎵'
              }}
            />
          ) : (
            '🎵'
          )}
        </div>
        <div id="pb-info">
          <p className="pb-title">{track.title}</p>
          <p className="pb-artist hint">{track.artist ?? '—'}</p>
        </div>
        <div id="pb-controls">
          <button className="icon-btn" title="Лайк" onClick={handleLike}>
            {liked ? '❤️' : '🤍'}
          </button>
          <button className="icon-btn" title="Пожаловаться" onClick={openComplaint}>
            🚩
          </button>
          <button className="play-btn" title="Воспроизвести" onClick={togglePlay}>
            {isPlaying ? '⏸' : '▶'}
          </button>
        </div>
      </div>
      <div id="pb-time">
        <span>{fmt(currentTime)}</span>
        <span>{fmt(duration)}</span>
      </div>
    </div>
  )
}
