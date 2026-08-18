import * as React from 'react'

/**
 * Spinner
 *
 * Loading indicator with pinging dot and ripple effect.
 * API matches shadcn/ui Spinner.
 *
 * @see https://ui.shadcn.com/docs/components/spinner
 *
 * @example
 * ```tsx
 * <Spinner />
 * <Spinner size="lg" />
 * ```
 */

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
    /** Size variant */
    size?: 'xs' | 'sm' | 'default' | 'md' | 'lg' | 'xl'
    /** Color variant */
    variant?: 'default' | 'accent' | 'muted' | 'inverse'
    /** Use pinging dot instead of rotating border */
    dot?: boolean
}

const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
    ({ className, size, variant, dot, ...props }, ref) => {
        const sizeClass = size && size !== 'default' ? `drams-spinner--${size}` : ''
        const variantClass = variant && variant !== 'default' ? `drams-spinner--${variant}` : ''
        const dotClass = dot ? 'drams-spinner--dot' : ''

        return (
            <div
                ref={ref}
                role="status"
                aria-label="Loading"
                className={`drams-spinner ${sizeClass} ${variantClass} ${dotClass} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Spinner.displayName = 'Spinner'

export { Spinner }
