import {
  Fragment,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import type { ArtistDetail } from '@/types/api'

interface Props {
  content: string
  /** Primary artist of the current track — the name the model will
   *  reference most often. Occurrences of this name become clickable. */
  trackArtist: string | null
  /** Navigate to the artist page (bound externally). */
  onOpenArtist?: (name: string) => void
}

type Token =
  | { kind: 'text'; value: string }
  | { kind: 'bold'; value: string }
  | { kind: 'italic'; value: string }
  | { kind: 'artist'; value: string }

function tokenizeLine(line: string, artistName: string | null): Token[] {
  // Pass 1: split markdown bold + italic.
  const md: Token[] = []
  const mdRe = /\*\*(.+?)\*\*|\*(.+?)\*/g
  let cursor = 0
  let m: RegExpExecArray | null
  while ((m = mdRe.exec(line)) !== null) {
    if (m.index > cursor) {
      md.push({ kind: 'text', value: line.slice(cursor, m.index) })
    }
    if (m[1] !== undefined) {
      md.push({ kind: 'bold', value: m[1] })
    } else if (m[2] !== undefined) {
      md.push({ kind: 'italic', value: m[2] })
    }
    cursor = m.index + m[0].length
  }
  if (cursor < line.length) {
    md.push({ kind: 'text', value: line.slice(cursor) })
  }

  // Pass 2: inside text-tokens, split artist-name occurrences (case
  // insensitive). Skip if name is too short or not provided.
  if (!artistName || artistName.trim().length < 2) return md
  const name = artistName.trim()
  const nameLower = name.toLowerCase()

  const out: Token[] = []
  for (const t of md) {
    if (t.kind !== 'text') {
      out.push(t)
      continue
    }
    const text = t.value
    const lower = text.toLowerCase()
    let cur = 0
    while (cur < text.length) {
      const idx = lower.indexOf(nameLower, cur)
      if (idx === -1) {
        out.push({ kind: 'text', value: text.slice(cur) })
        break
      }
      if (idx > cur) {
        out.push({ kind: 'text', value: text.slice(cur, idx) })
      }
      out.push({
        kind: 'artist',
        value: text.slice(idx, idx + name.length),
      })
      cur = idx + name.length
    }
  }
  return out
}

export function TrackInfoContent({
  content,
  trackArtist,
  onOpenArtist,
}: Props) {
  const [activeMention, setActiveMention] = useState<{
    name: string
    x: number
    y: number
  } | null>(null)

  // Split content by blank lines → paragraphs; keep single line breaks
  // inside a paragraph as <br/>.
  const paragraphs = content
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)

  const renderToken = useCallback(
    (t: Token, key: string): ReactNode => {
      if (t.kind === 'text') return <Fragment key={key}>{t.value}</Fragment>
      if (t.kind === 'bold')
        return <strong key={key}>{t.value}</strong>
      if (t.kind === 'italic') return <em key={key}>{t.value}</em>
      // artist
      return (
        <button
          key={key}
          type="button"
          className="tic-artist-mention"
          onClick={(e) => {
            e.stopPropagation()
            const rect =
              (e.currentTarget as HTMLElement).getBoundingClientRect()
            setActiveMention({
              name: t.value,
              x: rect.left + rect.width / 2,
              y: rect.bottom + 6,
            })
          }}
        >
          {t.value}
        </button>
      )
    },
    [],
  )

  return (
    <div className="tic-root">
      {paragraphs.map((para, pIdx) => {
        const lines = para.split('\n')
        return (
          <p key={pIdx} className="tic-paragraph">
            {lines.map((line, lIdx) => {
              const tokens = tokenizeLine(line, trackArtist)
              return (
                <Fragment key={lIdx}>
                  {tokens.map((t, i) =>
                    renderToken(t, `${pIdx}-${lIdx}-${i}`),
                  )}
                  {lIdx < lines.length - 1 && <br />}
                </Fragment>
              )
            })}
          </p>
        )
      })}

      {activeMention && (
        <ArtistPreviewPopover
          name={activeMention.name}
          x={activeMention.x}
          y={activeMention.y}
          onClose={() => setActiveMention(null)}
          onOpen={() => {
            const nm = activeMention.name
            setActiveMention(null)
            onOpenArtist?.(nm)
          }}
        />
      )}
    </div>
  )
}

interface PopoverProps {
  name: string
  x: number
  y: number
  onClose: () => void
  onOpen: () => void
}

function ArtistPreviewPopover({
  name,
  x,
  y,
  onClose,
  onOpen,
}: PopoverProps) {
  const [state, setState] = useState<
    | { kind: 'loading' }
    | { kind: 'notfound' }
    | { kind: 'error' }
    | { kind: 'ok'; artist: ArtistDetail }
  >({ kind: 'loading' })
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const resolved = await api.resolveArtistByName(name)
        if (cancelled) return
        if (!resolved) {
          setState({ kind: 'notfound' })
          return
        }
        const artist = await api.getArtist(resolved.id)
        if (cancelled) return
        setState({ kind: 'ok', artist })
      } catch {
        if (!cancelled) setState({ kind: 'error' })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [name])

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current) return
      if (!rootRef.current.contains(e.target as Node)) onClose()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  // Clamp to viewport: popover is ~280px wide, 120-180px tall.
  const viewportW =
    typeof window !== 'undefined' ? window.innerWidth : 400
  const viewportH =
    typeof window !== 'undefined' ? window.innerHeight : 800
  const popW = 280
  const popH = 200
  const left = Math.max(8, Math.min(x - popW / 2, viewportW - popW - 8))
  const top =
    y + popH > viewportH - 8 ? Math.max(8, y - popH - 32) : y

  return (
    <div
      ref={rootRef}
      className="tic-popover"
      style={{ left, top }}
      onClick={(e) => e.stopPropagation()}
    >
      {state.kind === 'loading' && (
        <div className="tic-popover-body tic-popover-muted">
          Загрузка…
        </div>
      )}
      {state.kind === 'notfound' && (
        <div className="tic-popover-body tic-popover-muted">
          Артист «{name}» не найден в каталоге.
        </div>
      )}
      {state.kind === 'error' && (
        <div className="tic-popover-body tic-popover-muted">
          Не удалось загрузить данные.
        </div>
      )}
      {state.kind === 'ok' && (
        <>
          <div className="tic-popover-body">
            <div className="tic-popover-avatar">
              {state.artist.image_url ? (
                <img src={state.artist.image_url} alt="" />
              ) : (
                <Icon name="user" size={28} />
              )}
            </div>
            <div className="tic-popover-text">
              <div className="tic-popover-name">
                {state.artist.name}
              </div>
              {state.artist.country && (
                <div className="tic-popover-meta">
                  {state.artist.country}
                </div>
              )}
              {state.artist.bio && (
                <div className="tic-popover-bio">
                  {state.artist.bio.length > 180
                    ? state.artist.bio.slice(0, 180).trimEnd() + '…'
                    : state.artist.bio}
                </div>
              )}
            </div>
          </div>
          <div className="tic-popover-actions">
            <button
              type="button"
              className="tic-popover-btn"
              onClick={onOpen}
            >
              Перейти
              <Icon name="chevron" size={14} />
            </button>
            <button
              type="button"
              className="tic-popover-close"
              onClick={onClose}
              aria-label="Закрыть"
            >
              <Icon name="x" size={14} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
