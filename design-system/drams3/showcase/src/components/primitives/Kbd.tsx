import * as React from 'react'

/**
 * Kbd
 *
 * Keyboard shortcut display component.
 * API matches shadcn/ui Kbd.
 *
 * @see https://ui.shadcn.com/docs/components/kbd
 *
 * @example
 * ```tsx
 * <KbdGroup>
 *   <Kbd>⌘</Kbd>
 *   <Kbd>K</Kbd>
 * </KbdGroup>
 * ```
 */

export interface KbdProps extends React.HTMLAttributes<HTMLElement> {
    /** Small size variant */
    size?: 'sm' | 'default'
    /** Accent color (for active/pressed keys) */
    accent?: boolean
}

const Kbd = React.forwardRef<HTMLElement, KbdProps>(
    ({ className, size, accent, ...props }, ref) => {
        const sizeClass = size === 'sm' ? 'drams-kbd--sm' : ''
        const accentClass = accent ? 'accent' : ''
        return (
            <kbd
                ref={ref}
                className={`drams-kbd ${sizeClass} ${accentClass} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Kbd.displayName = 'Kbd'

/* ═══════════════════════════════════════════════════════════════
   KBD GROUP
   Container for multiple keys.
   ═══════════════════════════════════════════════════════════════ */

export interface KbdGroupProps extends React.HTMLAttributes<HTMLSpanElement> {
    /** Hide the plus sign between keys */
    noPlus?: boolean
}

const KbdGroup = React.forwardRef<HTMLSpanElement, KbdGroupProps>(
    ({ className, noPlus, ...props }, ref) => {
        const noPlusClass = noPlus ? 'drams-kbd-group--no-plus' : ''
        return (
            <span
                ref={ref}
                className={`drams-kbd-group ${noPlusClass} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
KbdGroup.displayName = 'KbdGroup'

export { Kbd, KbdGroup }
