import * as React from 'react'
import * as SeparatorPrimitive from '@radix-ui/react-separator'

/**
 * Separator
 *
 * Visual divider between content sections.
 * API matches shadcn/ui Separator.
 *
 * @see https://ui.shadcn.com/docs/components/separator
 *
 * @example
 * ```tsx
 * <Separator />
 * <Separator orientation="vertical" />
 * ```
 */

export interface SeparatorProps
    extends React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root> {
    /** Visual variant */
    variant?: 'default' | 'subtle' | 'strong' | 'accent'
}

const Separator = React.forwardRef<
    React.ComponentRef<typeof SeparatorPrimitive.Root>,
    SeparatorProps
>(({ className, orientation = 'horizontal', decorative = true, variant, ...props }, ref) => {
    const variantClass = variant && variant !== 'default' ? `drams-separator--${variant}` : ''

    return (
        <SeparatorPrimitive.Root
            ref={ref}
            decorative={decorative}
            orientation={orientation}
            className={`drams-separator ${variantClass} ${className || ''}`.trim()}
            {...props}
        />
    )
})
Separator.displayName = SeparatorPrimitive.Root.displayName

export { Separator }
