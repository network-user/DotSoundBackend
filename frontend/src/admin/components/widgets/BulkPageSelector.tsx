import { useEffect, useState } from 'react'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'

interface Props {
  currentPage: number
  totalPages: number
  totalItems: number
  selectedCount: number
  disabled?: boolean
  fetchPageIds: (page: number) => Promise<number[]>
  fetchAllIds?: () => Promise<number[]>
  onAddIds: (ids: number[]) => void
  onClear: () => void
  onError?: (error: Error) => void | Promise<void>
}

function clampPage(value: number, totalPages: number): number {
  if (!Number.isFinite(value)) return 1
  return Math.max(1, Math.min(totalPages, Math.trunc(value)))
}

function mergeUnique(values: number[]): number[] {
  return Array.from(new Set(values))
}

export function BulkPageSelector({
  currentPage,
  totalPages,
  totalItems,
  selectedCount,
  disabled = false,
  fetchPageIds,
  fetchAllIds,
  onAddIds,
  onClear,
  onError,
}: Props) {
  const [fromPage, setFromPage] = useState(String(currentPage))
  const [toPage, setToPage] = useState(String(currentPage))
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setFromPage(String(currentPage))
    setToPage(String(currentPage))
  }, [currentPage])

  const canRun = !disabled && !busy && totalItems > 0
  const rangeStart = clampPage(Number(fromPage), totalPages)
  const rangeEnd = clampPage(Number(toPage), totalPages)
  const start = Math.min(rangeStart, rangeEnd)
  const end = Math.max(rangeStart, rangeEnd)

  async function collectPages(startPage: number, endPage: number) {
    if (!canRun) return
    setBusy(true)
    try {
      const ids: number[] = []
      for (let page = startPage; page <= endPage; page += 1) {
        ids.push(...(await fetchPageIds(page)))
      }
      onAddIds(mergeUnique(ids))
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err))
      await onError?.(error)
    } finally {
      setBusy(false)
    }
  }

  async function collectAll() {
    if (!canRun) return
    if (!fetchAllIds) {
      await collectPages(1, totalPages)
      return
    }
    setBusy(true)
    try {
      onAddIds(mergeUnique(await fetchAllIds()))
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err))
      await onError?.(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-bulk-pages" aria-label="Bulk selection">
      <div className="admin-bulk-pages__summary">
        <Icon name="check" size={14} />
        <span>{busy ? 'selecting...' : `${selectedCount} selected`}</span>
      </div>
      <MotionPress
        type="button"
        variant="ghost"
        disabled={!canRun}
        onClick={() => collectPages(currentPage, currentPage)}
      >
        Page
      </MotionPress>
      <label className="admin-bulk-pages__range">
        <input
          type="number"
          min={1}
          max={totalPages}
          value={fromPage}
          disabled={disabled || busy}
          onChange={(e) => setFromPage(e.target.value)}
          aria-label="From page"
        />
        <span>-</span>
        <input
          type="number"
          min={1}
          max={totalPages}
          value={toPage}
          disabled={disabled || busy}
          onChange={(e) => setToPage(e.target.value)}
          aria-label="To page"
        />
      </label>
      <MotionPress
        type="button"
        variant="ghost"
        disabled={!canRun}
        onClick={() => collectPages(start, end)}
      >
        Range
      </MotionPress>
      <MotionPress
        type="button"
        variant="ghost"
        disabled={!canRun}
        onClick={collectAll}
      >
        All filtered
      </MotionPress>
      <MotionPress
        type="button"
        variant="ghost"
        disabled={selectedCount === 0 || busy}
        onClick={onClear}
      >
        Clear
      </MotionPress>
    </div>
  )
}
