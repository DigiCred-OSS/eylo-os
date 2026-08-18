import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'

/**
 * Badge
 *
 * COMPOSITION: Badge is not a primitive — it's Box + Typography.
 * This React wrapper provides API compatibility with shadcn/ui.
 *
 * @see /compositions/badge.md
 *
 * @example
 * ```tsx
 * // Variants
 * <Badge>Default</Badge>
 * <Badge variant="secondary">Secondary</Badge>
 * <Badge variant="destructive">Destructive</Badge>
 * <Badge variant="outline">Outline</Badge>
 *
 * // Active state (replaces "accent" — semantic, not decorative)
 * <Badge active>Active</Badge>
 * <Badge variant="outline" active>Outline Active</Badge>
 *
 * // As link
 * <Badge asChild>
 *   <a href="/status">Status</a>
 * </Badge>
 * ```
 */

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
    /**
     * Visual variant of the badge
     */
    variant?: 'default' | 'secondary' | 'destructive' | 'outline'

    /**
     * Active state — indicates selection/active status.
     * Uses control.active token (Braun Orange).
     */
    active?: boolean

    /**
     * @deprecated Use `active` instead. Accent is semantic (active state), not decorative.
     */
    accent?: boolean

    /**
     * Render as child element (for links, etc.)
     */
    asChild?: boolean
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
    ({ className, variant = 'default', active, accent, asChild = false, ...props }, ref) => {
        const Comp = asChild ? Slot : 'div'

        // Support both 'active' and legacy 'accent' prop
        const isActive = active || accent

        return (
            <Comp
                ref={ref}
                data-composition="badge"
                data-variant={variant !== 'default' ? variant : undefined}
                data-active={isActive ? 'true' : undefined}
                className={className || undefined}
                {...props}
            />
        )
    }
)
Badge.displayName = 'Badge'

export { Badge }
