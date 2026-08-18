/**
 * DRAMS × Preact adapter
 *
 * This file is the entire Preact "binding" for DRAMS. It is deliberately small,
 * and it is the proof of the system's central claim: DRAMS is CSS plus a
 * contract, and a framework plugs into it by emitting that contract.
 *
 * There is no Radix here, no headless dependency, no shared code with the React
 * showcase — just Preact components that render `.drams-*` classes and the
 * documented data attributes. Every one of them supports `accent`, which is the
 * one place brand colour can enter.
 *
 * The contract, in full:
 *   class="drams-<name>"       selects the primitive
 *   data-variant / data-size   visual variant + size (omit for default)
 *   data-state                 runtime state: checked | active | on | open
 *   .accent / data-accent      opt into the brand
 */
import type { ComponentChildren, JSX } from 'preact'
import { useId, useState } from 'preact/hooks'

type Kids = { children?: ComponentChildren }
type Accent = { accent?: boolean }

const cx = (...parts: (string | false | undefined | null)[]) =>
    parts.filter(Boolean).join(' ')

/* ═══════════════════════════════════════════════ ACTION ═══ */

export function Button({
    variant, size, accent, children, ...rest
}: Kids & Accent & {
    variant?: 'outline' | 'secondary' | 'ghost' | 'destructive' | 'link'
    size?: 'xs' | 'sm' | 'lg' | 'icon'
} & JSX.ButtonHTMLAttributes<HTMLButtonElement>) {
    return (
        <button
            class={cx('drams-button', accent && 'accent')}
            data-variant={variant}
            data-size={size}
            {...rest}
        >
            {children}
        </button>
    )
}

export function ButtonGroup({ children }: Kids) {
    return <div data-composition="button-group">{children}</div>
}

/* ═══════════════════════════════════════════════ CONTENT ═══ */

export const Heading = ({ level = 2, children }: Kids & { level?: 1 | 2 | 3 | 4 }) => {
    const Tag = `h${level}` as 'h1'
    return <Tag class={`drams-h${level}`}>{children}</Tag>
}

export const Text = ({ size, tone, children }: Kids & {
    size?: 'sm' | 'lg'
    tone?: 'secondary' | 'muted'
}) => <p class={cx('drams-text', size && `drams-text--${size}`, tone && `drams-text--${tone}`)}>{children}</p>

export const Code = ({ children }: Kids) => <code class="drams-code">{children}</code>
export const Kbd = ({ children }: Kids) => <kbd class="drams-kbd">{children}</kbd>

export const Avatar = ({ name, status }: { name: string; status?: 'accent' | 'success' | 'warning' | 'error' }) => (
    <span class="drams-avatar">
        <span class="drams-avatar-fallback">
            {name.split(' ').map(w => w[0]).slice(0, 2).join('')}
        </span>
        {status ? <span class={`drams-avatar-badge drams-avatar-badge--${status}`} /> : null}
    </span>
)

export const Badge = ({ variant, active, accent, children }: Kids & Accent & {
    variant?: 'outline'
    active?: boolean
}) => (
    <span
        class={cx('drams-badge', accent && 'accent')}
        data-composition="badge"
        data-variant={variant}
        data-active={active ? 'true' : undefined}
    >
        {children}
    </span>
)

/* ═══════════════════════════════════════════════ INPUTS ═══ */

export function Input({ accent, ...rest }: Accent & JSX.InputHTMLAttributes<HTMLInputElement>) {
    return <input class={cx('drams-input', accent && 'accent')} {...rest} />
}

export function Textarea({ accent, ...rest }: Accent & JSX.TextareaHTMLAttributes<HTMLTextAreaElement>) {
    return <textarea class={cx('drams-textarea', accent && 'accent')} {...rest} />
}

export function Field({ label, children }: Kids & { label: string }) {
    return (
        <div class="drams-field">
            <label class="drams-label">{label}</label>
            {children}
        </div>
    )
}

/**
 * Slider
 *
 * DRAMS styles a COMPOSED slider — `.drams-slider-track` wrapping
 * `.drams-slider-range`, plus a `.drams-slider-thumb` — not a bare
 * `<input type="range">`. The React showcase gets that structure from Radix;
 * Preact has no Radix, so the adapter composes it directly.
 *
 * A real range input is layered over the top at zero opacity. It stays the
 * actual control, so keyboard stepping, drag, and screen-reader semantics come
 * from the platform rather than being reimplemented.
 */
export function Slider({ accent, min = 0, max = 100, value, label, ...rest }: Accent & {
    min?: number
    max?: number
    value: number
    label?: string
} & Omit<JSX.InputHTMLAttributes<HTMLInputElement>, 'value' | 'min' | 'max'>) {
    const pct = ((value - Number(min)) / (Number(max) - Number(min))) * 100
    return (
        <span
            class={cx('drams-slider', 'drams-slider--horizontal', accent && 'accent')}
            data-orientation="horizontal"
            style={{ position: 'relative', display: 'flex', width: '100%' }}
        >
            <span class="drams-slider-track" style={{ position: 'relative', flex: 1 }}>
                <span class="drams-slider-range" style={{ width: `${pct}%` }} />
            </span>
            <span
                class="drams-slider-thumb"
                style={{ position: 'absolute', left: `calc(${pct}% - 10px)`, pointerEvents: 'none' }}
            />
            <input
                type="range"
                min={min}
                max={max}
                value={value}
                aria-label={label}
                style={{
                    position: 'absolute', inset: 0, width: '100%', height: '100%',
                    opacity: 0, margin: 0, cursor: 'pointer',
                }}
                {...rest}
            />
        </span>
    )
}

/* ═══════════════════════════════════════════════ SELECTION ═══ */

export function Checkbox({ label, checked, onToggle, accent, disabled }: Accent & {
    label: string
    checked: boolean
    onToggle: (v: boolean) => void
    disabled?: boolean
}) {
    const id = useId()
    return (
        <div class="drams-flex drams-flex--items-center drams-flex--gap-2">
            <button
                id={id}
                type="button"
                role="checkbox"
                aria-checked={checked}
                disabled={disabled}
                class={cx('drams-checkbox', accent && 'accent')}
                data-state={checked ? 'checked' : 'unchecked'}
                onClick={() => onToggle(!checked)}
            >
                {checked ? (
                    <span class="drams-checkbox-indicator">
                        <svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
                            <path d="M8.5 2.5 4 7.5 1.5 5" stroke="currentColor" stroke-width="1.5"
                                fill="none" stroke-linecap="round" stroke-linejoin="round" />
                        </svg>
                    </span>
                ) : null}
            </button>
            <label class="drams-checkbox-label" for={id}>{label}</label>
        </div>
    )
}

export function Switch({ label, checked, onToggle, accent }: Accent & {
    label?: string
    checked: boolean
    onToggle: (v: boolean) => void
}) {
    return (
        <div class="drams-flex drams-flex--items-center drams-flex--gap-3">
            <button
                type="button"
                role="switch"
                aria-checked={checked}
                aria-label={label}
                class={cx('drams-switch', accent && 'accent')}
                data-state={checked ? 'checked' : 'unchecked'}
                onClick={() => onToggle(!checked)}
            >
                <span class="drams-switch-thumb" />
            </button>
            {label ? <span class="drams-switch-label">{label}</span> : null}
        </div>
    )
}

export function RadioGroup({ value, onChange, options, accent }: Accent & {
    value: string
    onChange: (v: string) => void
    options: { value: string; label: string }[]
}) {
    return (
        <div class="drams-radio-group" role="radiogroup">
            {options.map(o => (
                <div key={o.value} class="drams-flex drams-flex--items-center drams-flex--gap-2">
                    <button
                        type="button"
                        role="radio"
                        aria-checked={value === o.value}
                        class={cx('drams-radio', accent && 'accent')}
                        data-state={value === o.value ? 'checked' : 'unchecked'}
                        onClick={() => onChange(o.value)}
                    >
                        {value === o.value ? <span class="drams-radio-indicator" /> : null}
                    </button>
                    <label class="drams-radio-label">{o.label}</label>
                </div>
            ))}
        </div>
    )
}

/* ═══════════════════════════════════════════════ CONTAINERS ═══ */

export const Card = ({ children }: Kids) => <div class="drams-card">{children}</div>
export const CardHeader = ({ children }: Kids) => <div class="drams-card-header">{children}</div>
export const CardTitle = ({ children }: Kids) => <div class="drams-card-title">{children}</div>
export const CardDescription = ({ children }: Kids) => <div class="drams-card-description">{children}</div>
export const CardContent = ({ children }: Kids) => <div class="drams-card-content">{children}</div>

export function Collapsible({ trigger, children }: Kids & { trigger: string }) {
    // Native disclosure — no JS needed, and keyboard/AT behaviour is free.
    return (
        <details class="drams-box drams-box--bordered">
            <summary style={{ cursor: 'pointer' }}>{trigger}</summary>
            <div style={{ marginTop: 'var(--space-3)' }}>{children}</div>
        </details>
    )
}

/* ═══════════════════════════════════════════════ FEEDBACK ═══ */

export const Alert = ({ variant, title, children }: Kids & {
    variant?: 'destructive' | 'success' | 'warning' | 'info'
    title: string
}) => (
    <div class="drams-alert" data-composition="alert" data-variant={variant} role="alert">
        <div class="drams-alert-title">{title}</div>
        {children ? <div class="drams-alert-description">{children}</div> : null}
    </div>
)

export const Spinner = ({ accent }: Accent) => (
    <span class={cx('drams-spinner', accent && 'accent')} role="status" aria-label="Loading" />
)

export const Skeleton = ({ width, height }: { width?: number | string; height?: number | string }) => (
    <span class="drams-skeleton" style={{ width, height, display: 'block' }} />
)

/**
 * Progress
 *
 * `.drams-progress` wrapping `.drams-progress-indicator`, defined once in
 * `primitives/progress.css`. A second implementation used to live in
 * `feedback.css` with a `-bar` fill and a different track height; it was
 * removed, so there is no longer a choice to make here.
 */
export const Progress = ({ value, accent }: Accent & { value: number }) => (
    <div class={cx('drams-progress', accent && 'accent')} role="progressbar"
        aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
        <div class="drams-progress-indicator" style={{ width: `${value}%` }} />
    </div>
)

/* ═══════════════════════════════════════════════ LAYOUT ═══ */

export const Stack = ({ gap = 3, children }: Kids & { gap?: 2 | 3 | 4 | 6 | 8 }) => (
    <div class={`drams-stack drams-stack--${gap}`}>{children}</div>
)

export const Row = ({ gap = 3, children }: Kids & { gap?: 1 | 2 | 3 | 4 | 6 | 8 }) => (
    <div class={`drams-flex drams-flex--items-center drams-flex--wrap drams-flex--gap-${gap}`}>{children}</div>
)

export const Separator = ({ variant }: { variant?: 'subtle' | 'strong' | 'accent' }) => (
    <hr class={cx('drams-separator', variant && `drams-separator--${variant}`)}
        style={{ border: 0 }} />
)

/* ═══════════════════════════════════════════════ NAVIGATION ═══ */

export function Tabs({ tabs, accent }: Accent & { tabs: { value: string; label: string }[] }) {
    const [active, setActive] = useState(tabs[0].value)
    return (
        <div class="drams-tabs">
            <div class={cx('drams-tabs-list', accent && 'accent')} data-variant="line" role="tablist">
                {tabs.map(t => (
                    <button
                        key={t.value}
                        type="button"
                        role="tab"
                        aria-selected={active === t.value}
                        class="drams-tabs-trigger"
                        data-state={active === t.value ? 'active' : 'inactive'}
                        onClick={() => setActive(t.value)}
                    >
                        {t.label}
                    </button>
                ))}
            </div>
        </div>
    )
}

export const Breadcrumbs = ({ items }: { items: string[] }) => (
    <nav class="drams-breadcrumb-tabs-list" aria-label="Breadcrumb">
        {items.map((item, i) => (
            <span key={item} class="drams-flex drams-flex--items-center drams-flex--gap-3">
                <button type="button" class="drams-breadcrumb-tabs-trigger"
                    data-state={i === items.length - 1 ? 'active' : undefined}>
                    {item}
                </button>
                {i < items.length - 1 ? <span class="drams-breadcrumb-tabs-separator">/</span> : null}
            </span>
        ))}
    </nav>
)

/* ═══════════════════════════════════════════════ DATA ═══ */

export const Table = ({ children }: Kids) => <table class="drams-table">{children}</table>
export const List = ({ items }: { items: string[] }) => (
    <ul class="drams-stack drams-stack--2" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {items.map(i => <li key={i} class="drams-text drams-text--sm">{i}</li>)}
    </ul>
)
