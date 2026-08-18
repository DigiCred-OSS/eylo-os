import type { ReactNode } from 'react'

/** Showcase chrome. Deliberately plain markup — never Astryx components —
 *  so the frame is never mistaken for the thing being showcased. */

export function Showcase({ id, title, blurb, children }: {
    id: string
    title: string
    blurb: string
    children: ReactNode
}) {
    return (
        <section className="showcase" id={id}>
            <h2>{title}</h2>
            <p className="blurb">{blurb}</p>
            <div className="grid">{children}</div>
        </section>
    )
}

export function Demo({ title, children, note, column }: {
    title: string
    children: ReactNode
    note?: string
    column?: boolean
}) {
    return (
        <div className="demo">
            <h3>{title}</h3>
            <div className={column ? 'col' : 'row'}>{children}</div>
            {note ? <p className="note">{note}</p> : null}
        </div>
    )
}

/* Inline icons — IconButton takes a ReactNode, so no icon registry is needed. */
const svg = (d: string) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={d} />
    </svg>
)

export const icons = {
    plus: svg('M12 5v14M5 12h14'),
    search: svg('M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.3-4.3'),
    trash: svg('M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14'),
    check: svg('M20 6 9 17l-5-5'),
    chevron: svg('m6 9 6 6 6-6'),
}
