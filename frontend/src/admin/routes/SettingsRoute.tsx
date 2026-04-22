import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { useStepUp } from '../components/auth/StepUpDialog'
import { useCapability } from '../hooks/useCapability'

interface DeviceRow {
  id: number
  label: string | null
  fingerprint_hash_preview: string
  ip_first: string | null
  trusted_at: string | null
  last_seen_at: string | null
  created_at: string
}

interface FlagRow {
  key: string
  value: { enabled?: boolean }
  updated_by: number | null
  updated_at: string
}

export function SettingsRoute() {
  const { t } = useTranslation()
  const stepUp = useStepUp()
  const canManageFlags = useCapability(
    'feature_flags.manage',
  )
  const devices = useQuery({
    queryKey: ['admin', 'settings', 'devices'],
    queryFn: () => adminApi.listDevices(),
  })
  const flags = useQuery({
    queryKey: ['admin', 'settings', 'flags'],
    queryFn: () => adminApi.featureFlags(),
  })
  const [busyFlag, setBusyFlag] = useState<
    string | null
  >(null)

  async function toggleFlag(
    name: string,
    enabled: boolean,
  ) {
    const ok = await stepUp.request(
      'system.feature_flags.set',
    )
    if (!ok) return
    setBusyFlag(name)
    try {
      await adminApi.setFeatureFlag(
        name,
        enabled,
      )
      flags.refetch()
    } catch (err) {
      alert(
        (err as Error).message || 'failed',
      )
    } finally {
      setBusyFlag(null)
    }
  }

  async function revokeDevice(id: number) {
    if (
      !window.confirm(
        t('admin.settings.revokeConfirm'),
      )
    )
      return
    try {
      await adminApi.revokeDevice(id)
      devices.refetch()
    } catch (err) {
      alert(
        (err as Error).message || 'failed',
      )
    }
  }

  const deviceColumns: ColumnDef<DeviceRow>[] = [
    {
      header: 'Label',
      accessorKey: 'label',
      cell: (i) =>
        i.row.original.label ||
        t('admin.settings.noLabel'),
    },
    {
      header: 'Fingerprint',
      cell: (i) => (
        <span className="admin-mono">
          {
            i.row.original
              .fingerprint_hash_preview
          }
          …
        </span>
      ),
    },
    { header: 'IP', accessorKey: 'ip_first' },
    {
      header: 'Trusted',
      cell: (i) =>
        i.row.original.trusted_at ? (
          <StatusPill kind="ok">
            {t('admin.settings.trusted')}
          </StatusPill>
        ) : (
          <StatusPill kind="warn">
            {t('admin.settings.pending')}
          </StatusPill>
        ),
    },
    {
      header: 'Last seen',
      cell: (i) =>
        i.row.original.last_seen_at
          ? new Date(
              i.row.original.last_seen_at,
            ).toLocaleString()
          : '–',
    },
    {
      header: '',
      id: 'actions',
      cell: (i) => (
        <Press
          variant="ghost"
          onClick={() =>
            revokeDevice(i.row.original.id)
          }
        >
          {t('admin.settings.revoke')}
        </Press>
      ),
    },
  ]

  const flagColumns: ColumnDef<FlagRow>[] = [
    {
      header: 'Flag',
      accessorKey: 'key',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<string>()}
        </span>
      ),
    },
    {
      header: 'Enabled',
      cell: (i) =>
        i.row.original.value?.enabled ? (
          <StatusPill kind="ok">
            {t('admin.settings.on')}
          </StatusPill>
        ) : (
          <StatusPill kind="unknown">
            {t('admin.settings.off')}
          </StatusPill>
        ),
    },
    {
      header: 'Updated',
      cell: (i) =>
        new Date(
          i.row.original.updated_at,
        ).toLocaleString(),
    },
    {
      header: '',
      id: 'actions',
      cell: (i) => {
        if (!canManageFlags) return null
        const enabled = !!i.row.original.value
          ?.enabled
        return (
          <Press
            variant="ghost"
            disabled={
              busyFlag === i.row.original.key
            }
            onClick={() =>
              toggleFlag(
                i.row.original.key,
                !enabled,
              )
            }
          >
            {enabled
              ? t('admin.settings.disable')
              : t('admin.settings.enable')}
          </Press>
        )
      },
    },
  ]

  return (
    <div>
      <h1>{t('admin.settings.title')}</h1>
      <section className="admin-card">
        <h2>{t('admin.settings.trustedDevices')}</h2>
        <DataTable
          columns={deviceColumns}
          rows={
            (devices.data?.items ||
              []) as DeviceRow[]
          }
          emptyHint={t(
            'admin.settings.noDevices',
          )}
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.settings.featureFlags')}</h2>
        <FeatureFlagCreator
          onCreated={() => flags.refetch()}
          stepUp={stepUp}
        />
        <DataTable
          columns={flagColumns}
          rows={
            (flags.data?.items || []) as FlagRow[]
          }
          emptyHint={t('admin.settings.noFlags')}
        />
      </section>
      <AiEnrichmentSettings />
      <BackupsSection />
    </div>
  )
}

function AiEnrichmentSettings() {
  const { t } = useTranslation()
  const canManage = useCapability('settings.manage')
  const [trackTtl, setTrackTtl] = useState<string>('')
  const [artistTtl, setArtistTtl] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  const aiSettings = useQuery({
    queryKey: ['admin', 'settings', 'ai'],
    queryFn: () => adminApi.getAiSettings(),
    enabled: canManage,
  })

  useEffect(() => {
    if (aiSettings.data) {
      setTrackTtl(String(aiSettings.data.track_info_ttl_days))
      setArtistTtl(String(aiSettings.data.artist_supplemental_ttl_days))
    }
  }, [aiSettings.data])

  if (!canManage) return null

  async function handleSave() {
    const trackDays = parseInt(trackTtl, 10)
    const artistDays = parseInt(artistTtl, 10)
    if (!Number.isFinite(trackDays) || trackDays < 1) {
      alert('Track TTL must be >= 1')
      return
    }
    if (!Number.isFinite(artistDays) || artistDays < 1) {
      alert('Artist TTL must be >= 1')
      return
    }
    setBusy(true)
    setSaved(false)
    try {
      await adminApi.updateAiSettings({
        track_info_ttl_days: trackDays,
        artist_supplemental_ttl_days: artistDays,
      })
      aiSettings.refetch()
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      alert((err as Error).message || 'failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="admin-card">
      <h2>{t('admin.settings.aiEnrichment', { defaultValue: 'AI Enrichment' })}</h2>
      <p className="admin-card__sub">
        {t('admin.settings.aiEnrichmentDesc', {
          defaultValue: 'Configure cache TTL for AI-generated information. After expiry, next request triggers a fresh fetch.',
        })}
      </p>
      <div className="admin-toolbar" style={{ alignItems: 'flex-end', gap: 16 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
          {t('admin.settings.trackInfoTtl', { defaultValue: 'Track info cache (days)' })}
          <input
            type="number"
            min={1}
            value={trackTtl}
            onChange={(e) => setTrackTtl(e.target.value)}
            style={{ width: 80 }}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
          {t('admin.settings.artistSupplementalTtl', { defaultValue: 'Artist supplemental cache (days)' })}
          <input
            type="number"
            min={1}
            value={artistTtl}
            onChange={(e) => setArtistTtl(e.target.value)}
            style={{ width: 80 }}
          />
        </label>
        <Press variant="ghost" onClick={handleSave} disabled={busy}>
          {busy ? t('common.saving', { defaultValue: 'Saving…' }) : t('common.save', { defaultValue: 'Save' })}
        </Press>
        {saved && (
          <span style={{ color: '#4ade80', fontSize: 13 }}>
            {t('common.saved', { defaultValue: 'Saved' })}
          </span>
        )}
      </div>
    </section>
  )
}

function BackupsSection() {
  const { t } = useTranslation()
  const stepUp = useStepUp()
  const canRun = useCapability('backups.run')
  const canView = useCapability('backups.view')
  const [busy, setBusy] = useState(false)
  const list = useQuery({
    queryKey: ['admin', 'settings', 'backups'],
    queryFn: () => adminApi.listBackups(),
    enabled: canView,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  })

  async function handleRun(kind: string) {
    const ok = await stepUp.request(
      'system.backups.run',
    )
    if (!ok) return
    setBusy(true)
    try {
      const out = await adminApi.runBackup(kind)
      alert(
        `Backup queued: task ${out.task_id || '?'}`,
      )
      list.refetch()
    } catch (err) {
      alert((err as Error).message || 'failed')
    } finally {
      setBusy(false)
    }
  }

  if (!canView) return null

  const sections: Array<[
    string,
    Array<Record<string, unknown>>,
  ]> = [
    [
      'Daily',
      (list.data?.daily as Array<
        Record<string, unknown>
      >) || [],
    ],
    [
      'Weekly',
      (list.data?.weekly as Array<
        Record<string, unknown>
      >) || [],
    ],
    [
      'Monthly',
      (list.data?.monthly as Array<
        Record<string, unknown>
      >) || [],
    ],
  ]

  return (
    <section className="admin-card">
      <h2>{t('admin.settings.backups')}</h2>
      <p className="admin-card__sub">
        root: <code>{list.data?.root || '–'}</code>
        {list.data?.remote_configured
          ? ` · ${t(
              'admin.settings.remoteConfigured',
            )}`
          : ` · ${t(
              'admin.settings.remoteNotConfigured',
            )}`}
      </p>
      {canRun && (
        <div className="admin-toolbar">
          <Press
            variant="ghost"
            disabled={busy}
            onClick={() => handleRun('full')}
          >
            {t('admin.settings.runFull')}
          </Press>
          <Press
            variant="ghost"
            disabled={busy}
            onClick={() => handleRun('pg')}
          >
            {t('admin.settings.runPg')}
          </Press>
        </div>
      )}
      {sections.map(([label, items]) => (
        <div key={label}>
          <h3 className="admin-card__sub">
            {label} ({items.length})
          </h3>
          <DataTable<Record<string, unknown>>
            columns={[
              {
                header: 'Name',
                accessorKey: 'name',
                cell: (i) => (
                  <span className="admin-mono">
                    {i.getValue<string>()}
                  </span>
                ),
              },
              {
                header: 'Size',
                accessorKey: 'size_human',
              },
              {
                header: 'Modified',
                cell: (i) =>
                  new Date(
                    i.row.original
                      .modified_at as string,
                  ).toLocaleString(),
              },
            ]}
            rows={items}
            emptyHint="—"
          />
        </div>
      ))}
    </section>
  )
}

function FeatureFlagCreator({
  onCreated,
  stepUp,
}: {
  onCreated: () => void
  stepUp: ReturnType<typeof useStepUp>
}) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setName(name.replace(/[^a-z0-9._-]/gi, ''))
  }, [name])

  async function handleCreate() {
    if (!name) return
    const ok = await stepUp.request(
      'system.feature_flags.set',
    )
    if (!ok) return
    setBusy(true)
    try {
      await adminApi.setFeatureFlag(name, false)
      setName('')
      onCreated()
    } catch (err) {
      alert(
        (err as Error).message || 'failed',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-toolbar">
      <input
        type="text"
        placeholder="new feature flag name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={64}
      />
      <Press
        variant="ghost"
        onClick={handleCreate}
        disabled={!name || busy}
      >
        {busy ? 'Creating…' : 'Create'}
      </Press>
    </div>
  )
}
