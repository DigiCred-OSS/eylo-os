import * as React from 'react'
import * as ProgressPrimitive from '@radix-ui/react-progress'

/**
 * Progress
 *
 * Progress bar indicator.
 * API matches shadcn/ui Progress.
 *
 * @see https://ui.shadcn.com/docs/components/progress
 *
 * @example
 * ```tsx
 * <Progress value={33} />
 * ```
 */

export interface ProgressProps
    extends React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> {
    /** Progress value (0-100) */
    value?: number
    /** Size variant */
    size?: 'sm' | 'default' | 'lg'
    /** Status variant. Reports an outcome — not an interaction state. */
    variant?: 'default' | 'accent' | 'success' | 'warning' | 'error'
    /**
     * Render this control in the brand.
     *
     * Composes with every other prop rather than replacing them — an accented
     * progress bar is the same bar, filled in the brand.
     */
    accent?: boolean
    /** Indeterminate state (unknown progress) */
    indeterminate?: boolean
}

const Progress = React.forwardRef<
    React.ComponentRef<typeof ProgressPrimitive.Root>,
    ProgressProps
>(({ className, value, size, variant, accent, indeterminate, ...props }, ref) => {
    const sizeClass = size && size !== 'default' ? `drams-progress--${size}` : ''
    const variantClass = variant && variant !== 'default' ? `drams-progress--${variant}` : ''
    const indeterminateClass = indeterminate ? 'drams-progress--indeterminate' : ''

    return (
        <ProgressPrimitive.Root
            ref={ref}
            className={`drams-progress ${sizeClass} ${variantClass} ${indeterminateClass} ${accent ? 'accent' : ''} ${className || ''}`.trim()}
            {...props}
        >
            <ProgressPrimitive.Indicator
                className="drams-progress-indicator"
                style={{ width: indeterminate ? undefined : `${value || 0}%` }}
            />
        </ProgressPrimitive.Root>
    )
})
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
