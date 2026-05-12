import { ChangeEvent } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { AdminRangeSwitch } from './AdminRangeSwitch'

export type FilterDef =
  | {
      type: 'search'
      key: string
      placeholder?: string
      minWidth?: number
      ariaLabel?: string
    }
  | {
      type: 'tabs'
      key: string
      options: { value: string; label: string }[]
      ariaLabel?: string
      groupId?: string
    }
  | {
      type: 'select'
      key: string
      options: { value: string; label: string }[]
      placeholder?: string
      ariaLabel?: string
    }
  | {
      type: 'toggle'
      key: string
      label: string
    }

interface Props {
  filters: FilterDef[]
  values: Record<string, string | undefined>
  onChange: (key: string, value: string | undefined) => void
  ariaLabel?: string
}

export function FilterGroup({
  filters,
  values,
  onChange,
  ariaLabel,
}: Props) {
  return (
    <div
      className="admin-filter-group"
      role="group"
      aria-label={ariaLabel ?? 'Filters'}
    >
      {filters.map((f) => {
        if (f.type === 'search') {
          const cur = values[f.key] ?? ''
          const handle = (e: ChangeEvent<HTMLInputElement>) =>
            onChange(f.key, e.target.value || undefined)
          return (
            <label
              key={f.key}
              className="admin-filter-group__search"
              style={
                f.minWidth ? { minWidth: f.minWidth } : undefined
              }
            >
              <span className="admin-filter-group__icon" aria-hidden>
                <Icon name="search" size={14} />
              </span>
              <input
                type="search"
                value={cur}
                onChange={handle}
                placeholder={f.placeholder}
                aria-label={f.ariaLabel ?? f.placeholder ?? 'Search'}
              />
              {cur ? (
                <button
                  type="button"
                  className="admin-filter-group__clear"
                  onClick={() => onChange(f.key, undefined)}
                  aria-label="Clear search"
                >
                  <Icon name="x" size={12} />
                </button>
              ) : null}
            </label>
          )
        }

        if (f.type === 'tabs') {
          const cur = values[f.key] ?? f.options[0]?.value ?? ''
          return (
            <AdminRangeSwitch
              key={f.key}
              options={f.options}
              value={cur}
              onChange={(v) => onChange(f.key, String(v))}
              groupId={f.groupId ?? `filter-${f.key}`}
              ariaLabel={f.ariaLabel}
            />
          )
        }

        if (f.type === 'select') {
          const cur = values[f.key] ?? ''
          return (
            <label
              key={f.key}
              className="admin-filter-group__select"
              aria-label={f.ariaLabel}
            >
              <select
                value={cur}
                onChange={(e) =>
                  onChange(f.key, e.target.value || undefined)
                }
              >
                {f.placeholder ? (
                  <option value="">{f.placeholder}</option>
                ) : null}
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <span className="admin-filter-group__select-caret" aria-hidden>
                <Icon name="chevron-down" size={12} />
              </span>
            </label>
          )
        }

        const checked = values[f.key] === '1' || values[f.key] === 'true'
        return (
          <label key={f.key} className="admin-filter-group__toggle">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) =>
                onChange(f.key, e.target.checked ? '1' : undefined)
              }
            />
            <span>{f.label}</span>
          </label>
        )
      })}
    </div>
  )
}
