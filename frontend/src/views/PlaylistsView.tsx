import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import type { Playlist, PlaylistWithTracks } from '@/types/api'
import { TrackList } from '@/components/TrackList/TrackList'

type Screen = 'list' | 'detail'

export function PlaylistsView() {
  const [screen, setScreen] = useState<Screen>('list')
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null)
  const [selected, setSelected] = useState<PlaylistWithTracks | null>(null)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(false)

  const loadPlaylists = () => {
    const uid = getUserId()
    if (!uid) { setPlaylists([]); return }
    setPlaylists(null)
    api.getPlaylists(uid)
      .then(setPlaylists)
      .catch(() => setPlaylists([]))
  }

  useEffect(() => {
    loadPlaylists()
  }, [])

  const openPlaylist = async (p: Playlist) => {
    try {
      const detail = await api.getPlaylist(p.id)
      setSelected(detail)
      setScreen('detail')
    } catch { /* ignore */ }
  }

  const handleCreate = async () => {
    const uid = getUserId()
    if (!newName.trim() || !uid) return
    setLoading(true)
    try {
      await api.createPlaylist(uid, newName.trim())
      setNewName('')
      setCreating(false)
      loadPlaylists()
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  if (screen === 'detail' && selected) {
    return (
      <section
        id="view-playlists"
        className="view active"
      >
        <div className="view-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            className="icon-btn"
            onClick={() => { setScreen('list'); setSelected(null) }}
            style={{ fontSize: 22, padding: '4px 8px' }}
          >
            ←
          </button>
          <div>
            <h2 style={{ fontSize: 20 }}>{selected.name}</h2>
            <span className="hint">{selected.tracks.length} треков</span>
          </div>
        </div>
        <TrackList
          tracks={selected.tracks}
          emptyMessage="В этом плейлисте пока нет треков"
        />
      </section>
    )
  }

  return (
    <section id="view-playlists" className="view active">
      <div className="view-header">
        <h2>Плейлисты</h2>
        <span className="hint">Твои подборки</span>
      </div>

      <button
        className="create-playlist-btn"
        onClick={() => setCreating(true)}
      >
        <span className="icon">＋</span>
        Создать плейлист
      </button>

      {creating && (
        <div style={{ padding: '0 16px 16px' }}>
          <div className="form-group">
            <label className="form-label">Название плейлиста</label>
            <input
              id="new-playlist-name"
              className="form-input"
              placeholder="Мой плейлист"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="btn-secondary"
              style={{ flex: 1 }}
              onClick={() => { setCreating(false); setNewName('') }}
            >
              Отмена
            </button>
            <button
              id="create-playlist-submit"
              className="btn-primary"
              style={{ flex: 1, padding: '12px' }}
              onClick={handleCreate}
              disabled={!newName.trim() || loading}
            >
              {loading ? '...' : 'Создать'}
            </button>
          </div>
        </div>
      )}

      {playlists === null && <div className="loader" />}

      {playlists !== null && playlists.length === 0 && !creating && (
        <div className="empty-hint">
          <strong>Плейлистов пока нет</strong>
          Создай свою первую подборку
        </div>
      )}

      {playlists !== null && playlists.length > 0 && (
        <div className="playlist-list">
          {playlists.map((p) => (
            <div
              key={p.id}
              className="playlist-card"
              onClick={() => openPlaylist(p)}
            >
              <div className="playlist-cover">▤</div>
              <div className="playlist-info">
                <div className="playlist-name">{p.name}</div>
                <div className="playlist-meta">
                  {p.is_public ? 'Публичный' : 'Приватный'}
                </div>
              </div>
              <span className="playlist-chevron">›</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
