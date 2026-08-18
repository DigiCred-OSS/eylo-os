import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'

/**
 * Button component props
 *
 * API matches shadcn/ui Button exactly for drop-in replacement.
 * @see https://ui.shadcn.com/docs/components/button
 */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    /**
     * Visual variant of the button
     * - default: Dark/black button (matches shadcn)
     * - outline: Bordered, transparent background
     * - secondary: Muted filled background
     * - ghost: No visible surface until interaction
     * - destructive: For dangerous actions (Braun Red)
     * - link: Looks like a text link
     */
    variant?: 'default' | 'outline' | 'secondary' | 'ghost' | 'destructive' | 'link'

    /**
     * Accent modifier — uses Braun Orange instead of black.
     * Works with default and outline variants.
     */
    accent?: boolean

    /**
     * Size variant
     * - default: 36px height
     * - xs: 28px height
     * - sm: 32px height
     * - lg: 44px height
     * - icon: 36px square
     * - icon-xs: 28px square
     * - icon-sm: 32px square
     * - icon-lg: 44px square
     */
    size?: 'default' | 'xs' | 'sm' | 'lg' | 'icon' | 'icon-xs' | 'icon-sm' | 'icon-lg'

    /**
     * Change the default rendered element to the one passed as a child,
     * merging their props and behavior.
     *
     * Useful for rendering as a link or other element.
     * @example
     * ```tsx
     * <Button asChild>
     *   <a href="/home">Go Home</a>
     * </Button>
     * ```
     */
    asChild?: boolean

    /**
     * Custom class name
     */
    className?: string
}

/**
 * Button
 *
 * Physical button with machined appearance following Dieter Rams philosophy.
 * Press state uses shadow/elevation changes ONLY (no text color changes).
 *
 * API matches shadcn/ui Button for drop-in replacement.
 *
 * @example
 * ```tsx
 * <Button>Default (black)</Button>
 * <Button accent>Accent (Braun Orange)</Button>
 * <Button variant="outline">Outline</Button>
 * <Button variant="outline" accent>Outline Accent</Button>
 * <Button variant="secondary">Secondary</Button>
 * <Button variant="ghost">Ghost</Button>
 * <Button variant="destructive">Delete</Button>
 * <Button variant="link">Link</Button>
 * <Button size="sm">Small</Button>
 * <Button size="icon"><IconPlus /></Button>
 * <Button disabled>Disabled</Button>
 * ```
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({
        variant = 'default',
        size = 'default',
        accent,
        asChild = false,
        className = '',
        children,
        ...props
    }, ref) => {
        const Comp = asChild ? Slot : 'button'

        const dataAttrs: Record<string, string | boolean> = {}

        if (variant !== 'default') {
            dataAttrs['data-variant'] = variant
        }

        if (size !== 'default') {
            dataAttrs['data-size'] = size
        }

        return (
            <Comp
                ref={ref}
                className={`drams-button ${accent ? 'accent' : ''} ${className}`.trim()}
                {...dataAttrs}
                {...props}
            >
                {children}
            </Comp>
        )
    }
)

Button.displayName = 'Button'
