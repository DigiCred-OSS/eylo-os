import * as React from 'react'
import * as LabelPrimitive from '@radix-ui/react-label'

/**
 * Label
 *
 * Renders an accessible label associated with controls.
 * API matches shadcn/ui Label exactly.
 *
 * @see https://ui.shadcn.com/docs/components/label
 *
 * @example
 * ```tsx
 * <Label htmlFor="email">Your email address</Label>
 *
 * // With checkbox
 * <div className="flex items-center gap-2">
 *   <Checkbox id="terms" />
 *   <Label htmlFor="terms">Accept terms and conditions</Label>
 * </div>
 *
 * // Disabled state (peer styling)
 * <Label htmlFor="disabled-input" className="peer-disabled:opacity-70">
 *   Disabled field
 * </Label>
 * ```
 */
const Label = React.forwardRef<
    React.ComponentRef<typeof LabelPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
    <LabelPrimitive.Root
        ref={ref}
        className={`drams-label ${className || ''}`.trim()}
        {...props}
    />
))
Label.displayName = LabelPrimitive.Root.displayName

export { Label }
