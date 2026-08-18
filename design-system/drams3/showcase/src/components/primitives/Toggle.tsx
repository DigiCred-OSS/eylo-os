import * as React from 'react'
import * as TogglePrimitive from '@radix-ui/react-toggle'

/**
 * Toggle
 *
 * Two-state button that can be on or off.
 * API matches shadcn/ui Toggle.
 *
 * @see https://ui.shadcn.com/docs/components/toggle
 *
 * @example
 * ```tsx
 * <Toggle aria-label="Toggle italic">
 *   <ItalicIcon />
 * </Toggle>
 * ```
 */

export interface ToggleProps
    extends React.ComponentPropsWithoutRef<typeof TogglePrimitive.Root> {
    /** Visual variant */
    variant?: 'default' | 'outline'
    /** Size variant */
    size?: 'sm' | 'default' | 'lg'
    /** Accent color on pressed state */
    accent?: boolean
}

const Toggle = React.forwardRef<
    React.ComponentRef<typeof TogglePrimitive.Root>,
    ToggleProps
>(({ className, variant, size, accent, ...props }, ref) => {
    const variantClass = variant === 'outline' ? 'drams-toggle--outline' : ''
    const sizeClass = size && size !== 'default' ? `drams-toggle--${size}` : ''
    const accentClass = accent ? 'accent' : ''

    return (
        <TogglePrimitive.Root
            ref={ref}
            className={`drams-toggle ${variantClass} ${sizeClass} ${accentClass} ${className || ''}`.trim()}
            {...props}
        />
    )
})
Toggle.displayName = TogglePrimitive.Root.displayName

export { Toggle }
