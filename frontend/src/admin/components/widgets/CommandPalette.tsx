import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import {
  AdminCommand,
  useAdminCommands,
} from '../../hooks/useAdminCommands'

interface Props {
  open: boolean
  onClose: () => void
}

function score(query: string, cmd: AdminCommand): number {
  if (!query) return 1
  const q = query.toLowerCase()
  const fields = [
    cmd.title.toLowerCase(),
    cmd.subtitle?.toLowerCase() ?? '',
    cmd.group?.toLowerCase() ?? '',
    ...(cmd.keywords ?? []),
  ]
  let s = 0
  for (const f of fields) {
    if (!f) continue
    if (f === q) s += 10
    if (f.startsWith(q)) s += 6
    if (f.includes(q)) s += 3
    let qi = 0
    for (let i = 0; i < f.length && qi < q.length; i++) {
      if (f[i] === q[qi]) qi++
    }
    if (qi === q.length) s += 1
  }
  return s
}

export function CommandPalette({ open, onClose }: Props) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const commands = useAdminCommands(onClose)

  const results = useMemo(() => {
    const scored = commands
      .map((c) => ({ c, s: score(query, c) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
    return scored.map((x) => x.c)
  }, [commands, query])

  const grouped = useMemo(() => {
    const map = new Map<string, AdminCommand[]>()
    for (const cmd of results) {
      const key = cmd.group ?? 'Other'
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(cmd)
    }
    return Array.from(map.entries())
  }, [results])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActive(0)
    queueMicrotask(() => inputRef.current?.focus())
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    setActive(0)
  }, [query])

  const run = useCallback(
    (cmd?: AdminCommand) => {
      if (!cmd) return
      cmd.run()
      onClose()
    },
    [onClose],
  )

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActive((i) => Math.min(results.length - 1, i + 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActive((i) => Math.max(0, i - 1))
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        run(results[active])
      }
    },
    [active, onClose, results, run],
  )

  useEffect(() => {
    if (!listRef.current) return
    const el = listRef.current.querySelector<HTMLElement>(
      '[data-active="true"]',
    )
    el?.scrollIntoView({ block: 'nearest' })
  }, [active])

  if (!open) return null

  let flat = -1
  return (
    <div
      className="admin-modal-overlay admin-cmdk-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="admin-cmdk"
        role="dialog"
        aria-modal="true"
        aria-label={t('admin.cmdk.title', 'Command palette')}
        onKeyDown={onKey}
      >
        <div className="admin-cmdk__head">
          <span className="admin-cmdk__icon" aria-hidden>
            <Icon name="search" size={16} />
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t(
              'admin.cmdk.placeholder',
              'Search sections, jump to a page…',
            )}
            aria-label={t('admin.cmdk.title', 'Command palette')}
          />
          <kbd className="admin-cmdk__esc">esc</kbd>
        </div>
        <div className="admin-cmdk__list" ref={listRef}>
          {results.length === 0 ? (
            <div className="admin-cmdk__empty">
              {t('admin.cmdk.empty', 'No matches')}
            </div>
          ) : (
            grouped.map(([group, list]) => (
              <div key={group} className="admin-cmdk__group">
                <div className="admin-cmdk__group-label">{group}</div>
                {list.map((cmd) => {
                  flat++
                  const isActive = flat === active
                  return (
                    <button
                      key={cmd.id}
                      type="button"
                      data-active={isActive ? 'true' : 'false'}
                      className={
                        isActive
                          ? 'admin-cmdk__item is-active'
                          : 'admin-cmdk__item'
                      }
                      onMouseMove={() => setActive(flat)}
                      onClick={() => run(cmd)}
                    >
                      {cmd.icon ? (
                        <Icon
                          name={cmd.icon}
                          size={16}
                          className="admin-cmdk__item-icon"
                        />
                      ) : (
                        <span className="admin-cmdk__item-icon" aria-hidden />
                      )}
                      <span className="admin-cmdk__item-title">
                        {cmd.title}
                      </span>
                      {cmd.subtitle ? (
                        <span className="admin-cmdk__item-sub">
                          {cmd.subtitle}
                        </span>
                      ) : null}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
        <div className="admin-cmdk__foot">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd>{' '}
            {t('admin.cmdk.hintNav', 'navigate')}
          </span>
          <span>
            <kbd>↵</kbd>{' '}
            {t('admin.cmdk.hintGo', 'go')}
          </span>
          <span>
            <kbd>esc</kbd>{' '}
            {t('admin.cmdk.hintClose', 'close')}
          </span>
        </div>
      </div>
    </div>
  )
}
