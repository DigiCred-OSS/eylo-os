import * as React from 'react'

/**
 * Skeleton
 *
 * Loading placeholder with pulse animation.
 * API matches shadcn/ui Skeleton.
 *
 * @see https://ui.shadcn.com/docs/components/skeleton
 *
 * @example
 * ```tsx
 * <Skeleton className="h-4 w-[200px]" />
 * <Skeleton variant="avatar" />
 * ```
 */

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
    /** Shape variant */
    shape?: 'default' | 'circle' | 'rounded-full'
    /** Preset variant for common patterns */
    variant?: 'text' | 'text-sm' | 'text-lg' | 'heading' | 'avatar' | 'avatar-sm' | 'avatar-lg' | 'button' | 'input' | 'card'
    /** Disable animation */
    noAnimate?: boolean
}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
    ({ className, shape, variant, noAnimate, ...props }, ref) => {
        const shapeClass = shape ? `drams-skeleton--${shape}` : ''
        const variantClass = variant ? `drams-skeleton--${variant}` : ''
        const noAnimateClass = noAnimate ? 'drams-skeleton--no-animate' : ''

        return (
            <div
                ref={ref}
                className={`drams-skeleton ${shapeClass} ${variantClass} ${noAnimateClass} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Skeleton.displayName = 'Skeleton'

export { Skeleton }
