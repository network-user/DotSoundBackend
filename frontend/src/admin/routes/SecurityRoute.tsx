import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { useStepUp } from '../components/auth/StepUpDialog'

interface AttemptRow {
  id: number
  user_id: number | null
  ip: string | null
  ua: string | null
  success: boolean
  reason: string | null
  created_at: string
}

interface LockedRow {
  user_id: number
  ttl_seconds: number | null
}

const attemptColumns: ColumnDef<AttemptRow>[] = [
  {
    header: 'When',
    cell: (i) =>
      new Date(
        i.row.original.created_at,
      ).toLocaleString(),
  },
  { header: 'User', accessorKey: 'user_id' },
  { header: 'IP', accessorKey: 'ip' },
  {
    header: 'Result',
    cell: (i) =>
      i.row.original.success ? (
        <StatusPill kind="ok">success</StatusPill>
      ) : (
        <StatusPill kind="error">fail</StatusPill>
      ),
  },
  {
    header: 'Reason',
    accessorKey: 'reason',
  },
]

export function SecurityRoute() {
  const stepUp = useStepUp()
  const [failedOnly, setFailedOnly] =
    useState(true)
  const attempts = useQuery({
    queryKey: [
      'admin',
      'security',
      'attempts',
      failedOnly,
    ],
    queryFn: () =>
      adminApi.loginAttempts({
        failed_only: failedOnly,
        minutes: 240,
        limit: 200,
      }),
    refetchInterval: 10_000,
  })
  const locked = useQuery({
    queryKey: ['admin', 'security', 'locked'],
    queryFn: () => adminApi.lockedUsers(),
    refetchInterval: 5000,
  })

  async function handleRelease(userId: number) {
    const ok = await stepUp.request(
      'security.lockout.release',
    )
    if (!ok) return
    try {
      await adminApi.releaseLockout(userId)
      locked.refetch()
    } catch (err) {
      alert(
        (err as Error).message ||
          'release failed',
      )
    }
  }

  const lockedColumns: ColumnDef<LockedRow>[] = [
    { header: 'User', accessorKey: 'user_id' },
    {
      header: 'Lock TTL',
      cell: (i) =>
        i.row.original.ttl_seconds
          ? `${i.row.original.ttl_seconds}s`
          : '–',
    },
    {
      header: '',
      id: 'actions',
      cell: (i) => (
        <Press
          variant="ghost"
          onClick={() =>
            handleRelease(
              i.row.original.user_id,
            )
          }
        >
          Release
        </Press>
      ),
    },
  ]

  return (
    <div>
      <h1>Security</h1>
      <section className="admin-card">
        <h2>Locked admins</h2>
        <DataTable
          columns={lockedColumns}
          rows={
            (locked.data?.items || []) as LockedRow[]
          }
          emptyHint="No active lockouts"
        />
      </section>
      <section className="admin-card">
        <h2>Login attempts (last 4h)</h2>
        <div className="admin-toolbar">
          <label className="admin-checkbox">
            <input
              type="checkbox"
              checked={failedOnly}
              onChange={(e) =>
                setFailedOnly(
                  e.target.checked,
                )
              }
            />
            Failed only
          </label>
        </div>
        <DataTable
          columns={attemptColumns}
          rows={
            (attempts.data?.items ||
              []) as AttemptRow[]
          }
        />
      </section>
    </div>
  )
}
