import { useState } from 'react'
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'

interface Props<T> {
  columns: ColumnDef<T>[]
  rows: T[]
  emptyHint?: string
  enableSorting?: boolean
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
    onSortingChange: enableSorting
      ? setSorting
      : undefined,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: enableSorting
      ? getSortedRowModel()
      : undefined,
    enableSorting,
  })
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => {
                const canSort =
                  enableSorting &&
                  header.column.getCanSort()
                return (
                  <th key={header.id}>
                    {header.isPlaceholder ? null : canSort ? (
                      <button
                        type="button"
                        className="admin-table__sort-btn"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(
                          header.column.columnDef
                            .header,
                          header.getContext(),
                        )}
                        <span
                          className="admin-table__sort-ind"
                          aria-hidden
                        >
                          {header.column.getIsSorted() ===
                          'asc'
                            ? '↑'
                            : header.column.getIsSorted() ===
                                'desc'
                              ? '↓'
                              : '↕'}
                        </span>
                      </button>
                    ) : (
                      flexRender(
                        header.column.columnDef
                          .header,
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
                className="admin-table__empty"
              >
                {emptyHint}
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>
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
