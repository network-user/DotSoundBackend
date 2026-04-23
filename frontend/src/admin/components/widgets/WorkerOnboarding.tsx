import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Press } from '@/components/ui/Press'

interface Props {
  hasWorkers: boolean
}

interface Snippet {
  label: string
  body: string
}

function CopyBlock({
  snippets,
  copyLabel,
  copiedLabel,
}: {
  snippets: Snippet[]
  copyLabel: string
  copiedLabel: string
}) {
  const [copied, setCopied] = useState<string | null>(
    null,
  )

  const copy = async (label: string, body: string) => {
    try {
      await navigator.clipboard.writeText(body)
      setCopied(label)
      setTimeout(() => setCopied(null), 1500)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {snippets.map((s) => (
        <div key={s.label}>
          <div
            className="admin-card__sub"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>{s.label}</span>
            <Press
              variant="ghost"
              onClick={() => copy(s.label, s.body)}
            >
              {copied === s.label
                ? copiedLabel
                : copyLabel}
            </Press>
          </div>
          <pre
            className="admin-mono"
            style={{
              padding: 12,
              borderRadius: 6,
              background: 'var(--admin-bg-elev)',
              border:
                '1px solid var(--admin-border)',
              overflowX: 'auto',
              fontSize: 12,
              margin: '4px 0 0',
            }}
          >
            {s.body}
          </pre>
        </div>
      ))}
    </div>
  )
}

export function WorkerOnboarding({
  hasWorkers,
}: Props) {
  const { t } = useTranslation()
  const p = 'admin.audioCompute.onboarding' as const
  const [collapsed, setCollapsed] = useState(hasWorkers)
  const copyL = 'admin.audioCompute.copy' as const
  const copiedL = 'admin.audioCompute.copied' as const

  if (collapsed) {
    return (
      <section className="admin-card">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h2 style={{ margin: 0 }}>{t(`${p}.title`)}</h2>
          <Press
            variant="ghost"
            onClick={() => setCollapsed(false)}
          >
            {t(`${p}.show`)}
          </Press>
        </div>
      </section>
    )
  }

  return (
    <section className="admin-card">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h2 style={{ margin: 0 }}>{t(`${p}.title`)}</h2>
        <Press
          variant="ghost"
          onClick={() => setCollapsed(true)}
        >
          {t(`${p}.hide`)}
        </Press>
      </div>
      <p className="admin-card__sub">
        {t(`${p}.intro`)}
      </p>

      <ol style={{ paddingLeft: 20 }}>
        <li style={{ marginBottom: 16 }}>
          <strong>{t(`${p}.step1Title`)}</strong>{' '}
          {t(`${p}.step1Body`)}
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>{t(`${p}.step2Title`)}</strong>
          <CopyBlock
            copyLabel={t(copyL)}
            copiedLabel={t(copiedL)}
            snippets={[
              {
                label: t(`${p}.snippetCpuLabel`),
                body: t(`${p}.snippetCpuBody`),
              },
              {
                label: t(`${p}.snippetGpuLabel`),
                body: t(`${p}.snippetGpuBody`),
              },
            ]}
          />
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>
            {t(`${p}.whisperGpuTitle`)}
          </strong>
          <p
            className="admin-card__sub"
            style={{ marginTop: 8 }}
          >
            {t(`${p}.whisperGpuBody`)}
          </p>
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>{t(`${p}.step3Title`)}</strong>
          <ul>
            <li>
              {t(`${p}.step3ListName`)}
            </li>
            <li>
              {t(`${p}.step3ListProfile`)}
            </li>
            <li>
              {t(`${p}.step3ListCidrs`)}
            </li>
            <li>
              {t(`${p}.step3ListConc`)}
            </li>
          </ul>
          {t(`${p}.step3After`)}
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>{t(`${p}.step4Title`)}</strong>
          <CopyBlock
            copyLabel={t(copyL)}
            copiedLabel={t(copiedL)}
            snippets={[
              {
                label: t(`${p}.snippetEnvLabel`),
                body: t(`${p}.snippetEnvBody`),
              },
            ]}
          />
          {t(`${p}.step4After`)}
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>{t(`${p}.step5Title`)}</strong>
          <CopyBlock
            copyLabel={t(copyL)}
            copiedLabel={t(copiedL)}
            snippets={[
              {
                label: t(`${p}.snippetMakeLabel`),
                body: t(`${p}.snippetMakeBody`),
              },
              {
                label: t(`${p}.snippetSystemdLabel`),
                body: t(`${p}.snippetSystemdBody`),
              },
              {
                label: t(`${p}.snippetDockerLabel`),
                body: t(`${p}.snippetDockerBody`),
              },
            ]}
          />
        </li>

        <li>
          <strong>{t(`${p}.step6Title`)}</strong>
          {': '}
          {t(`${p}.step6Body`)}
        </li>
      </ol>

      <p className="admin-card__sub">
        {t(`${p}.protocolRef`)}
      </p>
    </section>
  )
}
