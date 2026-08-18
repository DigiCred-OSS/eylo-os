import * as React from 'react'

/**
 * Image
 *
 * Responsive image component with loading states.
 *
 * @example
 * ```tsx
 * <Image
 *   src="https://example.com/image.jpg"
 *   alt="Description"
 *   rounded
 * />
 * ```
 */

export interface ImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'loading'> {
    /** Object fit */
    fit?: 'cover' | 'contain' | 'fill' | 'none'
    /** Border radius variant */
    rounded?: boolean | 'lg' | 'circle'
    /** Show loading skeleton */
    isLoading?: boolean
    /** Native loading attribute */
    loading?: 'eager' | 'lazy'
}

const Image = React.forwardRef<HTMLImageElement, ImageProps>(
    ({ className, fit = 'cover', rounded, isLoading, loading, ...props }, ref) => {
        const fitClass = fit !== 'cover' ? `drams-image--${fit}` : ''
        const roundedClass = rounded === true
            ? 'drams-image--rounded'
            : rounded === 'lg'
                ? 'drams-image--rounded-lg'
                : rounded === 'circle'
                    ? 'drams-image--circle'
                    : ''
        const loadingClass = isLoading ? 'drams-image--loading' : ''

        return (
            <img
                ref={ref}
                loading={loading}
                className={`drams-image ${fitClass} ${roundedClass} ${loadingClass} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Image.displayName = 'Image'

/* ═══════════════════════════════════════════════════════════════
   ASPECT RATIO
   Container that maintains aspect ratio.
   ═══════════════════════════════════════════════════════════════ */

export interface AspectRatioProps extends React.HTMLAttributes<HTMLDivElement> {
    /** Aspect ratio as a number (e.g., 16/9 = 1.777) */
    ratio: number
}

const AspectRatio = React.forwardRef<HTMLDivElement, AspectRatioProps>(
    ({ className, ratio, style, children, ...props }, ref) => (
        <div
            ref={ref}
            className={`drams-aspect-ratio ${className || ''}`.trim()}
            style={{
                ...style,
                paddingBottom: `${100 / ratio}%`,
            }}
            {...props}
        >
            {children}
        </div>
    )
)
AspectRatio.displayName = 'AspectRatio'

export { AspectRatio, Image }
