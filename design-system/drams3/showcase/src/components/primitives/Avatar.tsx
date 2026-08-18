import * as React from 'react'
import * as AvatarPrimitive from '@radix-ui/react-avatar'

/**
 * Avatar
 *
 * User profile image with fallback.
 * API matches shadcn/ui Avatar exactly.
 *
 * @see https://ui.shadcn.com/docs/components/avatar
 *
 * @example
 * ```tsx
 * <Avatar>
 *   <AvatarImage src="https://github.com/shadcn.png" />
 *   <AvatarFallback>CN</AvatarFallback>
 * </Avatar>
 * ```
 */

export interface AvatarProps
    extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root> {
    /** Size of the avatar */
    size?: 'sm' | 'default' | 'lg' | 'xl'
    /** Accent border (for selected state) */
    accent?: boolean
}

const Avatar = React.forwardRef<
    React.ComponentRef<typeof AvatarPrimitive.Root>,
    AvatarProps
>(({ className, size, accent, ...props }, ref) => {
    const sizeClass = size && size !== 'default' ? `drams-avatar--${size}` : ''
    const accentClass = accent ? 'accent' : ''
    return (
        <AvatarPrimitive.Root
            ref={ref}
            className={`drams-avatar ${sizeClass} ${accentClass} ${className || ''}`.trim()}
            {...props}
        />
    )
})
Avatar.displayName = AvatarPrimitive.Root.displayName

const AvatarImage = React.forwardRef<
    React.ComponentRef<typeof AvatarPrimitive.Image>,
    React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image>
>(({ className, ...props }, ref) => (
    <AvatarPrimitive.Image
        ref={ref}
        className={`drams-avatar-image ${className || ''}`.trim()}
        {...props}
    />
))
AvatarImage.displayName = AvatarPrimitive.Image.displayName

const AvatarFallback = React.forwardRef<
    React.ComponentRef<typeof AvatarPrimitive.Fallback>,
    React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
>(({ className, ...props }, ref) => (
    <AvatarPrimitive.Fallback
        ref={ref}
        className={`drams-avatar-fallback ${className || ''}`.trim()}
        {...props}
    />
))
AvatarFallback.displayName = AvatarPrimitive.Fallback.displayName

/* ═══════════════════════════════════════════════════════════════
   AVATAR BADGE
   Status indicator positioned at bottom-right.
   ═══════════════════════════════════════════════════════════════ */

export interface AvatarBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    /** Status color variant */
    status?: 'default' | 'accent' | 'success' | 'warning' | 'error' | 'neutral'
}

const AvatarBadge = React.forwardRef<HTMLSpanElement, AvatarBadgeProps>(
    ({ className, status, ...props }, ref) => {
        const statusClass = status && status !== 'default' ? `drams-avatar-badge--${status}` : ''
        return (
            <span
                ref={ref}
                className={`drams-avatar-badge ${statusClass} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
AvatarBadge.displayName = 'AvatarBadge'

/* ═══════════════════════════════════════════════════════════════
   AVATAR GROUP
   Overlapping avatars for teams/groups.
   ═══════════════════════════════════════════════════════════════ */

export interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> { }

const AvatarGroup = React.forwardRef<HTMLDivElement, AvatarGroupProps>(
    ({ className, ...props }, ref) => (
        <div
            ref={ref}
            className={`drams-avatar-group ${className || ''}`.trim()}
            {...props}
        />
    )
)
AvatarGroup.displayName = 'AvatarGroup'

/* ═══════════════════════════════════════════════════════════════
   AVATAR GROUP COUNT
   Shows "+N" for additional members.
   ═══════════════════════════════════════════════════════════════ */

export interface AvatarGroupCountProps extends React.HTMLAttributes<HTMLSpanElement> { }

const AvatarGroupCount = React.forwardRef<HTMLSpanElement, AvatarGroupCountProps>(
    ({ className, ...props }, ref) => (
        <span
            ref={ref}
            className={`drams-avatar-group-count ${className || ''}`.trim()}
            {...props}
        />
    )
)
AvatarGroupCount.displayName = 'AvatarGroupCount'

export {
    Avatar,
    AvatarBadge,
    AvatarFallback,
    AvatarGroup,
    AvatarGroupCount,
    AvatarImage,
}
