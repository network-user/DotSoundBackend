import { useState } from 'react'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { adminApi } from '../lib/adminApi'

interface ArmDraft {
  name: string
  share: number
}

const STATUS_CYCLE = [
  'draft',
  'running',
  'paused',
  'completed',
] as const

function ExperimentDetail({
  experimentId,
}: {
  experimentId: number
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['recsys', 'exp-stats', experimentId],
    queryFn: () =>
      adminApi.experimentStats(experimentId),
    refetchInterval: 30_000,
  })
  if (isLoading || !data) {
    return <p>Загрузка статистики…</p>
  }
  const sig = data.significance
  return (
    <div className="adm-r-stack">
      <div>
        <strong>Назначения по плечам:</strong>{' '}
        {Object.entries(data.assignment_counts)
          .map(([arm, n]) => `${arm}: ${n}`)
          .join(' • ') || '—'}
      </div>
      <table className="adm-r-table">
        <thead>
          <tr>
            <th>Плечо</th>
            <th>Показы</th>
            <th>Завершённых</th>
            <th>Скипов</th>
            <th>Completion %</th>
            <th>Skip %</th>
          </tr>
        </thead>
        <tbody>
          {data.arm_outcomes.map((row) => (
            <tr key={row.arm}>
              <td>{row.arm}</td>
              <td>{row.impressions}</td>
              <td>{row.completed}</td>
              <td>{row.skipped}</td>
              <td>
                {(row.completion_rate * 100).toFixed(1)}
              </td>
              <td>{(row.skip_rate * 100).toFixed(1)}</td>
            </tr>
          ))}
          {data.arm_outcomes.length === 0 && (
            <tr>
              <td colSpan={6}>
                Нет данных — нужны impressions с
                experiment-tagged algorithm_version.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {sig && (
        <div className="adm-r-stack">
          <strong>
            Значимость ({sig.arm_a} vs {sig.arm_b}):
          </strong>
          <div>
            lift = {sig.lift.toFixed(4)}, z ={' '}
            {sig.z.toFixed(2)}, p ={' '}
            {sig.p_value_two_sided.toFixed(4)}
          </div>
          <div>
            {sig.sample_too_small
              ? 'Слишком мало данных для вывода.'
              : sig.significant
                ? '✅ Статистически значимо (α=0.05)'
                : 'Не значимо при α=0.05'}
          </div>
        </div>
      )}
    </div>
  )
}

function ExperimentRow({
  exp,
  expanded,
  onToggle,
  onStatusCycle,
  onDelete,
}: {
  exp: {
    id: number
    key: string
    arms: Record<string, number>
    status: string
  }
  expanded: boolean
  onToggle: () => void
  onStatusCycle: () => void
  onDelete: () => void
}) {
  return (
    <div className="adm-r-card">
      <div className="adm-r-row">
        <button
          type="button"
          className="adm-r-link"
          onClick={onToggle}
        >
          <strong>{exp.key}</strong>
          <span> #{exp.id}</span>
        </button>
        <span> [{exp.status}]</span>
        <span>
          {' arms: '}
          {Object.entries(exp.arms)
            .map(([k, v]) => `${k}:${v}`)
            .join(', ')}
        </span>
        <button type="button" onClick={onStatusCycle}>
          Сменить статус
        </button>
        <button type="button" onClick={onDelete}>
          Удалить
        </button>
      </div>
      {expanded && (
        <ExperimentDetail experimentId={exp.id} />
      )}
    </div>
  )
}

export function RecsysRoute() {
  const qc = useQueryClient()
  const { data: experiments = [] } = useQuery({
    queryKey: ['recsys', 'experiments'],
    queryFn: () => adminApi.listExperiments(),
  })

  const [draftKey, setDraftKey] = useState('')
  const [arms, setArms] = useState<ArmDraft[]>([
    { name: 'control', share: 50 },
    { name: 'variant', share: 50 },
  ])
  const [expanded, setExpanded] = useState<number | null>(
    null,
  )
  const [backfillLimit, setBackfillLimit] = useState(50)
  const [backfillResult, setBackfillResult] = useState<
    string | null
  >(null)

  const createMut = useMutation({
    mutationFn: () =>
      adminApi.createExperiment({
        key: draftKey.trim(),
        arms: Object.fromEntries(
          arms.map((a) => [a.name, a.share]),
        ),
      }),
    onSuccess: () => {
      setDraftKey('')
      qc.invalidateQueries({
        queryKey: ['recsys', 'experiments'],
      })
    },
  })

  const updateMut = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: number
      status: string
    }) =>
      adminApi.updateExperiment(id, { status }),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ['recsys', 'experiments'],
      }),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      adminApi.deleteExperiment(id),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ['recsys', 'experiments'],
      }),
  })

  const backfillMut = useMutation({
    mutationFn: () =>
      adminApi.backfillEmbeddings(backfillLimit),
    onSuccess: (res) =>
      setBackfillResult(
        `Поставлено в очередь ${res.enqueued_count} треков`,
      ),
    onError: (err: Error) =>
      setBackfillResult(`Ошибка: ${err.message}`),
  })

  return (
    <div className="adm-r-stack">
      <h2>Recsys — эксперименты и эмбеддинги</h2>

      <section className="adm-r-card">
        <h3>Создать эксперимент</h3>
        <div className="adm-r-row">
          <label>
            ключ:{' '}
            <input
              value={draftKey}
              onChange={(e) =>
                setDraftKey(e.target.value)
              }
              placeholder="daily_mix"
            />
          </label>
        </div>
        {arms.map((arm, idx) => (
          <div key={idx} className="adm-r-row">
            <input
              value={arm.name}
              onChange={(e) => {
                const next = [...arms]
                next[idx] = {
                  ...next[idx],
                  name: e.target.value,
                }
                setArms(next)
              }}
            />
            <input
              type="number"
              value={arm.share}
              onChange={(e) => {
                const next = [...arms]
                next[idx] = {
                  ...next[idx],
                  share: Number(e.target.value),
                }
                setArms(next)
              }}
            />
          </div>
        ))}
        <div className="adm-r-row">
          <button
            type="button"
            onClick={() =>
              setArms([
                ...arms,
                { name: '', share: 0 },
              ])
            }
          >
            + arm
          </button>
          <button
            type="button"
            disabled={
              !draftKey.trim() ||
              createMut.isPending
            }
            onClick={() => createMut.mutate()}
          >
            Создать
          </button>
        </div>
        {createMut.isError && (
          <p className="adm-r-error">
            {(createMut.error as Error).message}
          </p>
        )}
      </section>

      <section className="adm-r-stack">
        <h3>Эксперименты</h3>
        {experiments.map((exp) => (
          <ExperimentRow
            key={exp.id}
            exp={exp}
            expanded={expanded === exp.id}
            onToggle={() =>
              setExpanded((cur) =>
                cur === exp.id ? null : exp.id,
              )
            }
            onStatusCycle={() => {
              const idx = STATUS_CYCLE.indexOf(
                exp.status as (typeof STATUS_CYCLE)[number],
              )
              const next =
                STATUS_CYCLE[
                  (idx + 1) % STATUS_CYCLE.length
                ]
              updateMut.mutate({
                id: exp.id,
                status: next,
              })
            }}
            onDelete={() => {
              if (
                confirm(
                  `Удалить эксперимент ${exp.key}?`,
                )
              ) {
                deleteMut.mutate(exp.id)
              }
            }}
          />
        ))}
        {experiments.length === 0 && (
          <p>Экспериментов нет.</p>
        )}
      </section>

      <section className="adm-r-card">
        <h3>Audio embeddings — backfill</h3>
        <div className="adm-r-row">
          <label>
            limit:{' '}
            <input
              type="number"
              min={1}
              max={1000}
              value={backfillLimit}
              onChange={(e) =>
                setBackfillLimit(
                  Number(e.target.value) || 50,
                )
              }
            />
          </label>
          <button
            type="button"
            disabled={backfillMut.isPending}
            onClick={() => backfillMut.mutate()}
          >
            Поставить в очередь
          </button>
        </div>
        {backfillResult && <p>{backfillResult}</p>}
      </section>
    </div>
  )
}

export default RecsysRoute
