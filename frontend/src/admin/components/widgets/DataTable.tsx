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
  enableSorting?: boolean
}

function sortIconName(state: false | 'asc' | 'desc'): string | null {
  if (state === 'asc') return 'chevron-up'
  if (state === 'desc') return 'chevron-down'
  return null
}

export function DataTable<T>({
  columns,
  rows,
  emptyHint = 'No data',
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
          {table.getRowModel().rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="admin-table__empty adm-r-table__empty"
              >
                {emptyHint}
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
