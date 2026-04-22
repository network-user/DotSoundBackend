import { useState } from 'react'
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
}: {
  snippets: Snippet[]
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
              {copied === s.label ? 'Copied!' : 'Copy'}
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
  const [collapsed, setCollapsed] = useState(hasWorkers)

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
          <h2 style={{ margin: 0 }}>
            How to add a worker
          </h2>
          <Press
            variant="ghost"
            onClick={() => setCollapsed(false)}
          >
            Show
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
        <h2 style={{ margin: 0 }}>
          How to add a worker
        </h2>
        <Press
          variant="ghost"
          onClick={() => setCollapsed(true)}
        >
          Hide
        </Press>
      </div>
      <p className="admin-card__sub">
        A worker is a separate process (yours or
        someone else's machine) that pulls jobs and
        runs the heavy ASR. Backend never loads
        Whisper itself. The worker dials Backend
        outbound only — no inbound ports needed on
        its side.
      </p>

      <ol style={{ paddingLeft: 20 }}>
        <li style={{ marginBottom: 16 }}>
          <strong>Decide where it runs.</strong>{' '}
          Local machine for testing, a dedicated VPS
          / GPU box for prod. The worker needs
          outbound HTTPS to this Backend, ffmpeg
          installed, Python 3.12, and ~16 GB RAM
          (CPU large-v3) or ~8 GB VRAM (GPU).
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>Install the worker repo.</strong>
          <CopyBlock
            snippets={[
              {
                label: 'CPU install',
                body: `git clone <DotSoundComputeWorker repo URL>
cd DotSoundComputeWorker
poetry install --with cpu,dev`,
              },
              {
                label: 'GPU install (CUDA)',
                body: `git clone <DotSoundComputeWorker repo URL>
cd DotSoundComputeWorker
poetry install --with gpu,demucs,dev`,
              },
            ]}
          />
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>Create the worker here.</strong>{' '}
          Use the form in the Workers section
          below. Fill in:
          <ul>
            <li>
              <code>name</code> — anything
              memorable (e.g.{' '}
              <code>local-dev</code>,
              <code>vps-eu-1</code>).
            </li>
            <li>
              <code>profile</code> —
              <code>gpu_full</code> for the
              cascade's <code>remote_whisper</code>{' '}
              tier.
            </li>
            <li>
              <code>allowed_ip_cidrs</code> — the
              source IPs the worker will dial
              from. Use the presets (Localhost /
              Private LAN / Allow any).
            </li>
            <li>
              <code>max_concurrent_jobs</code> —
              how many jobs it can hold at once
              (default 1).
            </li>
          </ul>
          When you submit, Backend prints the
          generated <code>WORKER_SECRET</code>{' '}
          <strong>once</strong>. Copy it.
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>
            Drop credentials into the worker's
            .env.
          </strong>
          <CopyBlock
            snippets={[
              {
                label: '.env template',
                body: `WORKER_ID=<from step 3>
WORKER_SECRET=<from step 3>
WORKER_BACKEND_BASE_URL=https://your.backend.example
WORKER_DEBUG=false
WORKER_ASR_MODEL_SIZE=large-v3
WORKER_ASR_DEVICE=auto
WORKER_USE_DEMUCS=false
WORKER_METRICS_PORT=9100`,
              },
            ]}
          />
          The worker's <code>.env</code> is gitignored
          and is forbidden for any AI agent to
          read; only your shell touches it.
        </li>

        <li style={{ marginBottom: 16 }}>
          <strong>Start the worker.</strong>
          <CopyBlock
            snippets={[
              {
                label: 'foreground (dev)',
                body: 'make dev',
              },
              {
                label: 'production (systemd)',
                body: `[Service]
WorkingDirectory=/opt/DotSoundComputeWorker
EnvironmentFile=/opt/DotSoundComputeWorker/.env
ExecStart=/opt/DotSoundComputeWorker/.venv/bin/python -m worker
Restart=always
ReadOnlyPaths=/
RuntimeDirectory=worker-tmp
[Install]
WantedBy=multi-user.target`,
              },
              {
                label: 'docker (CPU)',
                body: `docker run -d --name dotsound-worker \\
  --read-only --tmpfs /tmp:size=2G \\
  --env-file .env \\
  -p 9100:9100 \\
  dotsound-compute-worker:cpu`,
              },
            ]}
          />
        </li>

        <li>
          <strong>Verify.</strong> Within ~15s the
          worker's row in the Workers table below
          should turn green ("active") and{' '}
          <code>last_seen</code> should tick. If it
          stays red, click on the worker to open
          its drawer and see the audit log:{' '}
          <code>auth_fail</code> means wrong
          secret, <code>404</code> means IP not in
          allowlist.
        </li>
      </ol>

      <p className="admin-card__sub">
        Full HMAC and protocol reference:{' '}
        <code>docs/compute-worker-protocol.md</code>{' '}
        in the Backend repo.
      </p>
    </section>
  )
}
