import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import type { SearchSuggestItem } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  onDone: (addedCount: number) => void
}

const SEARCH_DEBOUNCE_MS = 300
const MAX_RESULTS = 15
const MAX_SELECTED = 25

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function trackKey(it: SearchSuggestItem): number {
  return it.id
}

export function SearchImportPanel({ open, onClose, onDone }: Props) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<SearchSuggestItem[]>([])
  const [load, setLoad] = useState<LoadState>('idle')
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(),
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewId, setPreviewId] = useState<number | null>(null)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const debounceRef = useRef<number | null>(null)
  const reqTokenRef = useRef(0)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setItems([])
      setLoad('idle')
      setSelected(new Set())
      setSubmitting(false)
      setError(null)
      setPreviewId(null)
      const a = audioRef.current
      if (a) {
        try {
          a.pause()
          a.src = ''
        } catch {
          /* ignore */
        }
      }
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, submitting, onClose])

  useEffect(() => {
    if (!open) return
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    const q = query.trim()
    if (q.length === 0) {
      setItems([])
      setLoad('idle')
      return
    }
    setLoad('loading')
    debounceRef.current = window.setTimeout(async () => {
      reqTokenRef.current += 1
      const token = reqTokenRef.current
      try {
        const res = await api.searchSuggest(q, MAX_RESULTS)
        if (token !== reqTokenRef.current) return
        const tracks = (res.items || []).filter(
          (x) => x.kind === 'track',
        )
        setItems(tracks)
        setLoad('ready')
      } catch {
        if (token !== reqTokenRef.current) return
        setItems([])
        setLoad('error')
      }
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [open, query])

  const toggleSelected = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < MAX_SELECTED) {
        next.add(id)
      }
      return next
    })
  }, [])

  const togglePreview = useCallback(
    (id: number) => {
      const a = audioRef.current
      if (!a) return
      if (previewId === id && !a.paused) {
        try {
          a.pause()
        } catch {
          /* ignore */
        }
        setPreviewId(null)
        return
      }
      try {
        a.pause()
        a.muted = false
        a.src = `/api/v1/tracks/${id}/audio?force_progressive=true`
      } catch {
        /* ignore */
      }
      const p = a.play()
      if (!p) {
        setPreviewId(id)
        return
      }
      p.then(() => setPreviewId(id)).catch(() => {
        setPreviewId(null)
        setError(
          t('redesign.onboardingV2.importSearch.previewBlocked'),
        )
      })
    },
    [previewId, t],
  )

  const handleSubmit = useCallback(async () => {
    if (selected.size === 0 || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const trackIds = Array.from(selected)
      const res = await api.seedOnboardingTracks(trackIds)
      const added = (res.liked ?? 0) + (res.skipped ?? 0)
      onDone(added)
    } catch {
      setError(t('redesign.onboardingV2.importSearch.fail'))
      setSubmitting(false)
    }
  }, [selected, submitting, t, onDone])

  const handleBackdrop = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget && !submitting) onClose()
    },
    [submitting, onClose],
  )

  const selectedCount = selected.size

  const ctaLabel = useMemo(() => {
    if (submitting) return '…'
    if (selectedCount === 0)
      return t('redesign.onboardingV2.importSearch.submitEmpty')
    return t('redesign.onboardingV2.importSearch.submit', {
      count: selectedCount,
    })
  }, [submitting, selectedCount, t])

  if (!open) return null

  return (
    <div className="modal" onClick={handleBackdrop}>
      <div className="modal-content search-import-modal">
        <div className="modal-header">
          <h3>{t('redesign.onboardingV2.importSearch.modalTitle')}</h3>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn"
            ariaLabel={t('redesign.onboardingV2.importSearch.close')}
            onClick={onClose}
            disabled={submitting}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </div>
        <p className="modal-hint">
          {t('redesign.onboardingV2.importSearch.modalHint')}
        </p>
        <div className="form-group">
          <input
            className="form-input"
            type="search"
            inputMode="search"
            autoComplete="off"
            placeholder={t(
              'redesign.onboardingV2.importSearch.placeholder',
            )}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={submitting}
            autoFocus
          />
        </div>
        <div className="search-import-results">
          {load === 'loading' && (
            <p className="onboarding-subtitle">
              {t('redesign.onboardingV2.importSearch.loading')}
            </p>
          )}
          {load === 'ready' && items.length === 0 && (
            <p className="onboarding-subtitle">
              {t('redesign.onboardingV2.importSearch.empty')}
            </p>
          )}
          {load === 'error' && (
            <p className="form-error">
              {t('redesign.onboardingV2.importSearch.fail')}
            </p>
          )}
          {items.map((it) => {
            const id = trackKey(it)
            const isSelected = selected.has(id)
            const isPlaying = previewId === id
            return (
              <label
                key={id}
                className={
                  'search-import-item' +
                  (isSelected ? ' is-selected' : '')
                }
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleSelected(id)}
                  disabled={submitting}
                />
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="light"
                  className="search-import-play"
                  ariaLabel="preview"
                  onClick={(e) => {
                    e.preventDefault()
                    togglePreview(id)
                  }}
                  disabled={submitting}
                >
                  <Icon
                    name={isPlaying ? 'pause' : 'play-fill'}
                    size={16}
                  />
                </MotionPress>
                <div className="search-import-meta">
                  <span className="search-import-title">
                    {it.title || '—'}
                  </span>
                  <span className="search-import-artist">
                    {it.name || ''}
                  </span>
                </div>
              </label>
            )
          })}
        </div>
        {error && <div className="form-error">{error}</div>}
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          className="btn-primary"
          disabled={selectedCount === 0 || submitting}
          onClick={() => void handleSubmit()}
        >
          {ctaLabel}
        </MotionPress>
        <audio ref={audioRef} preload="none" hidden />
      </div>
    </div>
  )
}
