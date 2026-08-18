import * as React from 'react'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'

/**
 * Checkbox component props
 *
 * API matches shadcn/ui Checkbox exactly.
 * Uses Radix UI Checkbox primitive.
 * @see https://ui.shadcn.com/docs/components/checkbox
 */
export interface CheckboxProps
    extends React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> {
    /**
     * Accent variant - uses Braun Orange for indicator instead of black
     */
    accent?: boolean

    /**
     * Custom class name
     */
    className?: string
}

/**
 * Checkbox
 *
 * A control that allows the user to toggle between checked and not checked.
 * Uses Radix UI Checkbox primitive with DRAMS3 styling.
 * Indicator is a small colored square (Braun-style, not a checkmark).
 *
 * @example
 * ```tsx
 * // Uncontrolled
 * <Checkbox defaultChecked />
 *
 * // Controlled
 * const [checked, setChecked] = React.useState(false)
 * <Checkbox checked={checked} onCheckedChange={setChecked} />
 *
 * // With label (use with Field component)
 * <Field>
 *   <Checkbox id="terms" />
 *   <FieldLabel htmlFor="terms">Accept terms</FieldLabel>
 * </Field>
 *
 * // Invalid state
 * <Checkbox aria-invalid />
 *
 * // Disabled
 * <Checkbox disabled />
 * ```
 */
export const Checkbox = React.forwardRef<
    React.ElementRef<typeof CheckboxPrimitive.Root>,
    CheckboxProps
>(({ className = '', accent, ...props }, ref) => (
    <CheckboxPrimitive.Root
        ref={ref}
        className={`drams-checkbox ${accent ? 'accent' : ''} ${className}`.trim()}
        {...props}
    >
        <CheckboxPrimitive.Indicator className="drams-checkbox-indicator" />
    </CheckboxPrimitive.Root>
))

Checkbox.displayName = CheckboxPrimitive.Root.displayName
