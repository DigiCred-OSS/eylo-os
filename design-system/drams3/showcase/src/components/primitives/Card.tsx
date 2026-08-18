import * as React from 'react'

/**
 * Card component props
 *
 * API matches shadcn/ui Card exactly for drop-in replacement.
 * @see https://ui.shadcn.com/docs/components/card
 */
export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
    /**
     * Visual variant
     * - default: Raised surface with shadow
     * - inset: Recessed surface
     * - outline: Border only, no shadow
     * - ghost: No visible container until hover
     */
    variant?: 'default' | 'inset' | 'outline' | 'ghost'

    /**
     * Size variant — affects padding
     * - default: Standard padding
     * - sm: Compact padding
     * - lg: Spacious padding
     */
    size?: 'default' | 'sm' | 'lg'

    /**
     * Interactive card — adds hover lift effect
     */
    interactive?: boolean

    /**
     * Custom class name
     */
    className?: string
}

/**
 * Card
 *
 * Content container with physical surface appearance.
 * Raised from background with subtle shadow depth.
 *
 * @example
 * ```tsx
 * <Card>
 *   <CardHeader>
 *     <CardTitle>Card Title</CardTitle>
 *     <CardDescription>Card description goes here.</CardDescription>
 *   </CardHeader>
 *   <CardContent>
 *     <p>Main content area</p>
 *   </CardContent>
 *   <CardFooter>
 *     <Button>Action</Button>
 *   </CardFooter>
 * </Card>
 * ```
 */
const Card = React.forwardRef<HTMLDivElement, CardProps>(
    ({ variant = 'default', size = 'default', interactive, className = '', ...props }, ref) => {
        const dataAttrs: Record<string, string | boolean> = {}

        if (variant !== 'default') {
            dataAttrs['data-variant'] = variant
        }
        if (size !== 'default') {
            dataAttrs['data-size'] = size
        }
        if (interactive) {
            dataAttrs['data-interactive'] = 'true'
        }

        return (
            <div
                ref={ref}
                className={`drams-card ${className}`.trim()}
                {...dataAttrs}
                {...props}
            />
        )
    }
)
Card.displayName = 'Card'

/**
 * CardHeader
 *
 * Container for title and description.
 */
const CardHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className = '', ...props }, ref) => (
    <div
        ref={ref}
        className={`drams-card-header ${className}`.trim()}
        {...props}
    />
))
CardHeader.displayName = 'CardHeader'

/**
 * CardTitle
 *
 * Card heading.
 */
const CardTitle = React.forwardRef<
    HTMLHeadingElement,
    React.HTMLAttributes<HTMLHeadingElement>
>(({ className = '', ...props }, ref) => (
    <h3
        ref={ref}
        className={`drams-card-title ${className}`.trim()}
        {...props}
    />
))
CardTitle.displayName = 'CardTitle'

/**
 * CardDescription
 *
 * Secondary text below the title.
 */
const CardDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
>(({ className = '', ...props }, ref) => (
    <p
        ref={ref}
        className={`drams-card-description ${className}`.trim()}
        {...props}
    />
))
CardDescription.displayName = 'CardDescription'

/**
 * CardContent
 *
 * Main content area.
 */
const CardContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className = '', ...props }, ref) => (
    <div
        ref={ref}
        className={`drams-card-content ${className}`.trim()}
        {...props}
    />
))
CardContent.displayName = 'CardContent'

/**
 * CardFooter
 *
 * Actions area, typically for buttons.
 */
const CardFooter = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className = '', ...props }, ref) => (
    <div
        ref={ref}
        className={`drams-card-footer ${className}`.trim()}
        {...props}
    />
))
CardFooter.displayName = 'CardFooter'

/**
 * CardAction
 *
 * Action element positioned in top-right of header.
 * Use for buttons, badges, or other interactive elements.
 */
const CardAction = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className = '', ...props }, ref) => (
    <div
        ref={ref}
        className={`drams-card-action ${className}`.trim()}
        {...props}
    />
))
CardAction.displayName = 'CardAction'

export {
    Card,
    CardHeader,
    CardTitle,
    CardDescription,
    CardAction,
    CardContent,
    CardFooter
}
