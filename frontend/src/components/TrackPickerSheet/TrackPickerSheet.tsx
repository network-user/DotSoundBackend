import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Sheet } from '@/components/ui/Sheet'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import type { SearchSuggestItem, LikedTrack } from '@/types/api'

type Props = {
  open: boolean
  onClose: () => void
  onAdd: (trackId: number) => Promise<void>
  excludeIds: Set<number>
  addingId: number | null
}

type PickerItem = {
  id: number
  title: string
  artist: string | null
  cover_key?: string | null
}

const DEBOUNCE_MS = 280
const SUGGEST_LIMIT = 20
const DEFAULT_LIKED_SIZE = 25

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function fromSuggest(src: SearchSuggestItem): PickerItem {
  return {
    id: src.id,
    title: src.title ?? '—',
    artist: src.name,
    cover_key: src.cover_key,
  }
}

function fromLiked(src: LikedTrack): PickerItem {
  return {
    id: src.id,
    title: src.title,
    artist: src.artist,
    cover_key: src.cover_key,
  }
}

export function TrackPickerSheet({
  open,
  onClose,
  onAdd,
  excludeIds,
  addingId,
}: Props) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [defaultItems, setDefaultItems] = useState<
    PickerItem[]
  >([])
  const [searchItems, setSearchItems] = useState<PickerItem[]>(
    [],
  )
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const debounceRef = useRef<number | null>(null)
  const reqTokenRef = useRef(0)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setSearchItems([])
      setLoadState('idle')
      return
    }
    const uid = getUserId()
    if (!uid) {
      setDefaultItems([])
      return
    }
    api
      .getLikedTracks(uid, 1, DEFAULT_LIKED_SIZE)
      .then((res) => {
        setDefaultItems(res.items.map(fromLiked))
      })
      .catch(() => setDefaultItems([]))
  }, [open])

  useEffect(() => {
    if (!open) return
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current)
    }
    const q = query.trim()
    if (q.length === 0) {
      setSearchItems([])
      setLoadState('idle')
      return
    }
    setLoadState('loading')
    debounceRef.current = window.setTimeout(async () => {
      reqTokenRef.current += 1
      const token = reqTokenRef.current
      try {
        const res = await api.searchSuggest(q, SUGGEST_LIMIT)
        if (token !== reqTokenRef.current) return
        const tracks = (res.items ?? [])
          .filter((x) => x.kind === 'track')
          .map(fromSuggest)
        setSearchItems(tracks)
        setLoadState('ready')
      } catch {
        if (token !== reqTokenRef.current) return
        setSearchItems([])
        setLoadState('error')
      }
    }, DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current)
      }
    }
  }, [open, query])

  const handleAdd = useCallback(
    async (id: number) => {
      await onAdd(id)
    },
    [onAdd],
  )

  const isSearching = query.trim().length > 0
  const source = isSearching ? searchItems : defaultItems
  const visible = source.filter((it) => !excludeIds.has(it.id))

  return (
    <Sheet
      open={open}
      onClose={onClose}
      snap="tall"
      ariaLabel={t('redesign.library.trackPickerTitle')}
    >
      <div className="tp-sheet">
        <h2 className="tp-sheet__title">
          {t('redesign.library.trackPickerTitle')}
        </h2>

        <div className="tp-sheet__search-wrap">
          <Icon
            name="search"
            size={15}
            className="tp-sheet__search-icon"
          />
          <input
            className="tp-sheet__search-input"
            type="search"
            inputMode="search"
            autoComplete="off"
            placeholder={t(
              'redesign.library.trackPickerPlaceholder',
            )}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query.length > 0 && (
            <MotionPress
              type="button"
              variant="icon"
              haptic="light"
              className="tp-sheet__clear"
              ariaLabel="Очистить"
              onClick={() => setQuery('')}
            >
              <Icon name="x" size={14} />
            </MotionPress>
          )}
        </div>

        {!isSearching && (
          <p className="tp-sheet__section-label">
            {t('redesign.library.trackPickerLikedSection')}
          </p>
        )}

        <div className="tp-sheet__list" role="list">
          {loadState === 'loading' && (
            <p className="tp-sheet__hint">
              {t('redesign.library.trackPickerLoading')}
            </p>
          )}
          {loadState === 'error' && (
            <p className="tp-sheet__hint tp-sheet__hint--error">
              {t('redesign.library.trackPickerError')}
            </p>
          )}
          {loadState !== 'loading' && visible.length === 0 && (
            <p className="tp-sheet__hint">
              {isSearching
                ? t('redesign.library.trackPickerEmpty')
                : t(
                    'redesign.library.trackPickerEmptyLiked',
                  )}
            </p>
          )}
          {visible.map((it) => {
            const coverSrc = it.cover_key
              ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(
                  it.cover_key,
                )}`
              : null
            const isAdding = addingId === it.id
            return (
              <div
                key={it.id}
                className="tp-sheet__row"
                role="listitem"
              >
                <div className="tp-sheet__row-cover">
                  {coverSrc ? (
                    <img
                      src={coverSrc}
                      alt=""
                      className="tp-sheet__row-cover-img"
                      loading="lazy"
                    />
                  ) : (
                    <div className="tp-sheet__row-cover-fallback">
                      <Icon name="music" size={14} />
                    </div>
                  )}
                </div>
                <div className="tp-sheet__row-meta">
                  <span className="tp-sheet__row-title">
                    {it.title}
                  </span>
                  {it.artist && (
                    <span className="tp-sheet__row-artist">
                      {it.artist}
                    </span>
                  )}
                </div>
                <MotionPress
                  type="button"
                  variant="icon"
                  haptic="light"
                  className="tp-sheet__row-add"
                  ariaLabel={t(
                    'redesign.library.trackPickerAdd',
                  )}
                  disabled={addingId !== null}
                  onClick={() => void handleAdd(it.id)}
                >
                  {isAdding ? (
                    <span className="tp-sheet__row-adding">
                      …
                    </span>
                  ) : (
                    <Icon name="plus" size={18} />
                  )}
                </MotionPress>
              </div>
            )
          })}
        </div>
      </div>
    </Sheet>
  )
}
