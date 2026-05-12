import { useState } from 'react'
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'

interface Props<T> {
  columns: ColumnDef<T>[]
  rows: T[]
  emptyHint?: string
  emptyTitle?: string
  emptyIcon?: string
  isLoading?: boolean
  loadingRows?: number
  error?: string | null
  onRetry?: () => void
  enableSorting?: boolean
}

function sortIconName(state: false | 'asc' | 'desc'): string | null {
  if (state === 'asc') return 'chevron-up'
  if (state === 'desc') return 'chevron-down'
  return null
}

function SkeletonRows({ count, cols }: { count: number; cols: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, r) => (
        <tr key={`sk-${r}`} className="adm-r-table__row admin-table__row--skel">
          {Array.from({ length: cols }).map((_, c) => (
            <td
              key={`sk-${r}-${c}`}
              className="adm-r-table__cell admin-table__cell--skel"
            >
              <span className="admin-skel-bar" aria-hidden />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

export function DataTable<T>({
  columns,
  rows,
  emptyHint = 'No data',
  emptyTitle,
  emptyIcon = 'empty-staff',
  isLoading = false,
  loadingRows = 6,
  error = null,
  onRetry,
  enableSorting = false,
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const table = useReactTable({
    data: rows,
    columns,
    state: enableSorting ? { sorting } : undefined,
    onSortingChange: enableSorting ? setSorting : undefined,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: enableSorting ? getSortedRowModel() : undefined,
    enableSorting,
  })

  const showLoading = isLoading && rows.length === 0
  const showError = !!error && rows.length === 0 && !isLoading
  const showEmpty =
    !showLoading && !showError && table.getRowModel().rows.length === 0

  return (
    <div className="admin-table-wrap adm-r-table-wrap">
      <table className="admin-table adm-r-table">
        <thead className="adm-r-table__head">
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => {
                const canSort =
                  enableSorting && header.column.getCanSort()
                const sortState = header.column.getIsSorted()
                return (
                  <th key={header.id} className="adm-r-table__th">
                    {header.isPlaceholder ? null : canSort ? (
                      <MotionPress
                        type="button"
                        variant="ghost"
                        className="admin-table__sort-btn adm-r-table__sort"
                        haptic="selection"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {sortIconName(sortState) && (
                          <span
                            className="admin-table__sort-ind adm-r-table__sort-ind"
                            aria-hidden
                          >
                            <Icon
                              name={sortIconName(sortState) as string}
                              size={12}
                            />
                          </span>
                        )}
                      </MotionPress>
                    ) : (
                      flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )
                    )}
                  </th>
                )
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {showLoading ? (
            <SkeletonRows count={loadingRows} cols={columns.length} />
          ) : showError ? (
            <tr>
              <td
                colSpan={columns.length}
                className="admin-table__state admin-table__state--error"
              >
                <div className="admin-table__state-icon" aria-hidden>
                  <Icon name="alert-triangle" size={28} />
                </div>
                <div className="admin-table__state-text">{error}</div>
                {onRetry ? (
                  <MotionPress
                    type="button"
                    variant="ghost"
                    onClick={onRetry}
                    className="admin-table__state-action"
                  >
                    <Icon name="refresh" size={14} />
                    <span>Retry</span>
                  </MotionPress>
                ) : null}
              </td>
            </tr>
          ) : showEmpty ? (
            <tr>
              <td
                colSpan={columns.length}
                className="admin-table__empty adm-r-table__empty admin-table__state"
              >
                <div className="admin-table__state-icon" aria-hidden>
                  <Icon name={emptyIcon} size={32} />
                </div>
                {emptyTitle ? (
                  <div className="admin-table__state-title">{emptyTitle}</div>
                ) : null}
                <div className="admin-table__state-text">{emptyHint}</div>
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="adm-r-table__row">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="adm-r-table__cell">
                    {flexRender(
                      cell.column.columnDef.cell,
                      cell.getContext(),
                    )}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
