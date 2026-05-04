import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { trackProgressiveAudioUrl } from '@/lib/offlineCache'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface TrackRow {
  id: number
  title: string
  artist: string | null
  source: string | null
  genre?: string | null
  is_active: boolean
  uploaded_by_id: number | null
  created_at: string
}

interface ContextState {
  trackId: number
  content: string | null
  status: string
}

interface PromptState {
  prompt: string
  lang: string
}

export function TracksRoute() {
  const { t } = useTranslation()
  const { showConfirm, showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [playingId, setPlayingId] = useState<number | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  // context feature state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [promptModal, setPromptModal] = useState<PromptState | null>(null)
  const [contextModal, setContextModal] = useState<ContextState | null>(null)
  const [contextEditValue, setContextEditValue] = useState('')
  const [busyContext, setBusyContext] = useState(false)
  const [batchPromptModal, setBatchPromptModal] = useState<string | null>(null)
  const [importModal, setImportModal] = useState(false)
  const [importText, setImportText] = useState('')
  const [importResult, setImportResult] = useState<{
    imported: number
    errors: string[]
  } | null>(null)

  const contextTextareaRef = useRef<HTMLTextAreaElement>(null)

  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'tracks', page, search],
    queryFn: () =>
      adminApi.listTracks({
        page,
        size: 25,
        search: search || undefined,
      }),
    placeholderData: keepPreviousData,
  })
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const rows = (data?.items || []) as unknown as TrackRow[]

  useEffect(() => {
    setSelectedIds(new Set())
  }, [page])

  const refresh = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'tracks'] })

  const handleDelete = async (id: number, title: string) => {
    const ok = await showConfirm(
      t('admin.tracks.confirmDelete', { id, title }),
      { danger: true },
    )
    if (!ok) return
    setBusyId(id)
    try {
      await adminApi.deleteTrack(id)
      refresh()
    } catch (err) {
      await showAlert(
        t('admin.tracks.deleteFailed', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusyId(null)
    }
  }

  const handleToggleVisibility = async (id: number, isActive: boolean) => {
    setBusyId(id)
    try {
      await adminApi.setTrackVisibility(id, !isActive)
      refresh()
    } catch {}
    finally {
      setBusyId(null)
    }
  }

  const handleGenreChange = async (id: number, genre: string) => {
    setBusyId(id)
    try {
      await adminApi.updateTrackGenre(id, genre || null)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleOpen = (id: number) => {
    window.open(`/mini_app/track/${id}`, '_blank')
  }

  const handleTogglePlay = (id: number) => {
    setPlayingId((prev) => (prev === id ? null : id))
  }

  const handlePrompt = async (id: number) => {
    setBusyId(id)
    try {
      const res = await adminApi.getTrackPrompt(id)
      setPromptModal({ prompt: res.prompt, lang: res.language })
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleContext = async (id: number) => {
    setBusyId(id)
    try {
      const res = await adminApi.getTrackContext(id)
      setContextEditValue(res.content ?? '')
      setContextModal({ trackId: id, content: res.content, status: res.status })
      setTimeout(() => contextTextareaRef.current?.focus(), 50)
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleSaveContext = async () => {
    if (!contextModal) return
    setBusyContext(true)
    try {
      await adminApi.setTrackContext(contextModal.trackId, contextEditValue)
      setContextModal(null)
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyContext(false)
    }
  }

  const handleClearContext = async () => {
    if (!contextModal) return
    const ok = await showConfirm('Очистить контекст трека?', { danger: true })
    if (!ok) return
    setBusyContext(true)
    try {
      await adminApi.clearTrackContext(contextModal.trackId)
      setContextModal(null)
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyContext(false)
    }
  }

  const handleBatchPrompt = async () => {
    const ids = Array.from(selectedIds)
    try {
      const res = await adminApi.batchPrompt(ids)
      setBatchPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleImport = async () => {
    try {
      const res = await adminApi.batchImport(importText)
      setImportResult(res)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selectedIds.has(r.id))

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(rows.map((r) => r.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const toggleSelectOne = (id: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      checked ? next.add(id) : next.delete(id)
      return next
    })
  }

  const columns: ColumnDef<TrackRow>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={allOnPageSelected}
          onChange={(e) => toggleSelectAll(e.target.checked)}
          aria-label="Выбрать все"
        />
      ),
      cell: (i) => (
        <input
          type="checkbox"
          checked={selectedIds.has(i.row.original.id)}
          onChange={(e) => toggleSelectOne(i.row.original.id, e.target.checked)}
          aria-label={`Выбрать трек ${i.row.original.id}`}
        />
      ),
      enableSorting: false,
    },
    {
      header: t('admin.tracks.colId'),
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">{i.getValue<number>()}</span>
      ),
    },
    {
      header: t('admin.tracks.colTitle'),
      accessorKey: 'title',
      cell: (i) => (
        <button
          type="button"
          className="admin-link"
          onClick={() => handleOpen(i.row.original.id)}
        >
          {i.row.original.title}
        </button>
      ),
    },
    {
      header: t('admin.tracks.colArtist'),
      accessorKey: 'artist',
    },
    {
      header: t('admin.tracks.colSource'),
      accessorKey: 'source',
    },
    {
      header: 'Жанр',
      accessorKey: 'genre',
      cell: (i) => (
        <input
          type="text"
          defaultValue={i.row.original.genre || ''}
          placeholder="Без жанра"
          onBlur={(e) => {
            if (e.target.value !== (i.row.original.genre || '')) {
              handleGenreChange(i.row.original.id, e.target.value)
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.currentTarget.blur()
            }
          }}
          style={{ width: 120, padding: '4px 8px', fontSize: 13, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--surface-1)', color: 'var(--text)' }}
          disabled={busyId === i.row.original.id}
        />
      ),
    },
    {
      header: t('admin.tracks.colStatus'),
      accessorKey: 'is_active',
      cell: (i) =>
        i.row.original.is_active ? (
          <StatusPill kind="ok">{t('admin.tracks.visible')}</StatusPill>
        ) : (
          <StatusPill kind="warn">{t('admin.tracks.hidden')}</StatusPill>
        ),
    },
    {
      header: t('admin.tracks.colUploaded'),
      accessorKey: 'created_at',
      cell: (i) =>
        new Date(i.row.original.created_at).toLocaleDateString(),
    },
    {
      header: '',
      id: 'actions',
      enableSorting: false,
      cell: (i) => {
        const { id, title, is_active } = i.row.original
        const busy = busyId === id
        const isPlaying = playingId === id
        return (
          <div
            style={{
              display: 'flex',
              gap: 6,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <Press
              variant="ghost"
              onClick={() => handleTogglePlay(id)}
              disabled={busy}
            >
              {isPlaying
                ? t('admin.tracks.actionPause')
                : t('admin.tracks.actionPlay')}
            </Press>
            {isPlaying && (
              <audio
                src={trackProgressiveAudioUrl(id)}
                controls
                autoPlay
                style={{ height: 28, maxWidth: 180 }}
              />
            )}
            <Press
              variant="ghost"
              onClick={() => handleToggleVisibility(id, is_active)}
              disabled={busy}
            >
              {is_active
                ? t('admin.tracks.actionHide')
                : t('admin.tracks.actionShow')}
            </Press>
            <Press
              variant="ghost"
              onClick={() => handleOpen(id)}
              disabled={busy}
            >
              {t('admin.tracks.actionOpen')}
            </Press>
            <Press
              variant="ghost"
              onClick={() => handlePrompt(id)}
              disabled={busy}
            >
              Промпт
            </Press>
            <Press
              variant="ghost"
              onClick={() => handleContext(id)}
              disabled={busy}
            >
              Контекст
            </Press>
            <Press
              variant="ghost"
              onClick={() => handleDelete(id, title)}
              disabled={busy}
            >
              {t('admin.tracks.actionDelete')}
            </Press>
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <h1>{t('admin.tracks.title')}</h1>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t('admin.tracks.searchPlaceholder')}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Press
          variant="ghost"
          disabled={selectedIds.size === 0}
          onClick={handleBatchPrompt}
        >
          Batch Prompt ({selectedIds.size})
        </Press>
        <Press
          variant="ghost"
          onClick={() => {
            setImportText('')
            setImportResult(null)
            setImportModal(true)
          }}
        >
          Импорт ответа AI
        </Press>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        enableSorting
      />
      <div className="admin-pagination">
        <Press
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t('admin.common.prev')}
        </Press>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <Press
          variant="ghost"
          disabled={page >= totalPages || isFetching}
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </Press>
      </div>

      {/* Prompt modal */}
      {promptModal && (
        <div
          className="admin-modal-overlay"
          onClick={() => setPromptModal(null)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 640 }}
          >
            <h3>
              Промпт для нейросети&nbsp;
              <span style={{ fontSize: 12, fontWeight: 400 }}>
                [{promptModal.lang.toUpperCase()}]
              </span>
            </h3>
            <textarea
              readOnly
              value={promptModal.prompt}
              rows={18}
              style={{
                width: '100%',
                fontFamily: 'monospace',
                fontSize: 13,
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Press
                variant="primary"
                onClick={() =>
                  navigator.clipboard.writeText(promptModal.prompt)
                }
              >
                Копировать
              </Press>
              <Press variant="ghost" onClick={() => setPromptModal(null)}>
                Закрыть
              </Press>
            </div>
          </div>
        </div>
      )}

      {/* Context edit modal */}
      {contextModal && (
        <div
          className="admin-modal-overlay"
          onClick={() => !busyContext && setContextModal(null)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 560 }}
          >
            <h3>Контекст — трек #{contextModal.trackId}</h3>
            <p
              style={{
                fontSize: 12,
                color: 'var(--text-secondary)',
                margin: '0 0 8px',
              }}
            >
              Статус: {contextModal.status}
            </p>
            <textarea
              ref={contextTextareaRef}
              value={contextEditValue}
              onChange={(e) => setContextEditValue(e.target.value)}
              rows={10}
              maxLength={5000}
              style={{ width: '100%', resize: 'vertical' }}
              disabled={busyContext}
              placeholder="Введите описание трека (3–5 предложений)..."
            />
            <p
              style={{
                fontSize: 11,
                color: 'var(--text-secondary)',
                margin: '2px 0 8px',
                textAlign: 'right',
              }}
            >
              {contextEditValue.length} / 5000
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <Press
                variant="primary"
                onClick={handleSaveContext}
                disabled={busyContext || !contextEditValue.trim()}
              >
                Сохранить
              </Press>
              <Press
                variant="ghost"
                onClick={handleClearContext}
                disabled={busyContext}
              >
                Очистить
              </Press>
              <Press
                variant="ghost"
                onClick={() => setContextModal(null)}
                disabled={busyContext}
              >
                Отмена
              </Press>
            </div>
          </div>
        </div>
      )}

      {/* Batch prompt modal */}
      {batchPromptModal && (
        <div
          className="admin-modal-overlay"
          onClick={() => setBatchPromptModal(null)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 700 }}
          >
            <h3>Batch Prompt ({selectedIds.size} треков)</h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
              Скопируйте и вставьте в нейросеть. Ответ вставьте через «Импорт ответа AI».
            </p>
            <textarea
              readOnly
              value={batchPromptModal}
              rows={22}
              style={{
                width: '100%',
                fontFamily: 'monospace',
                fontSize: 12,
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Press
                variant="primary"
                onClick={() =>
                  navigator.clipboard.writeText(batchPromptModal)
                }
              >
                Копировать
              </Press>
              <Press variant="ghost" onClick={() => setBatchPromptModal(null)}>
                Закрыть
              </Press>
            </div>
          </div>
        </div>
      )}

      {/* Import modal */}
      {importModal && (
        <div
          className="admin-modal-overlay"
          onClick={() => setImportModal(false)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 640 }}
          >
            <h3>Импорт ответа AI</h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
              Вставьте JSON-ответ нейросети. Контекст будет распределён по трекам автоматически.
            </p>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={14}
              placeholder={
                '{"tracks":[{"id":1,"content":"..."},{"id":2,"content":"..."}]}'
              }
              style={{
                width: '100%',
                fontFamily: 'monospace',
                fontSize: 12,
                resize: 'vertical',
              }}
            />
            {importResult && (
              <div style={{ marginTop: 8 }}>
                <p style={{ fontWeight: 600 }}>
                  Импортировано: {importResult.imported}
                </p>
                {importResult.errors.length > 0 && (
                  <ul
                    style={{
                      fontSize: 12,
                      color: 'var(--color-danger, #c00)',
                      paddingLeft: 16,
                      margin: '4px 0 0',
                    }}
                  >
                    {importResult.errors.map((e, idx) => (
                      <li key={idx}>{e}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Press
                variant="primary"
                onClick={handleImport}
                disabled={!importText.trim()}
              >
                Импортировать
              </Press>
              <Press variant="ghost" onClick={() => setImportModal(false)}>
                Закрыть
              </Press>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
