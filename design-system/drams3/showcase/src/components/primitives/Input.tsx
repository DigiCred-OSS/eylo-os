import * as React from 'react'

/**
 * Input
 *
 * A text input component for forms and user data entry.
 * API matches shadcn/ui Input exactly.
 *
 * @see https://ui.shadcn.com/docs/components/input
 *
 * @example
 * ```tsx
 * // Basic
 * <Input placeholder="Enter text..." />
 *
 * // With type
 * <Input type="email" placeholder="email@example.com" />
 *
 * // Disabled
 * <Input disabled placeholder="Disabled" />
 *
 * // Invalid (use aria-invalid)
 * <Input aria-invalid placeholder="Invalid input" />
 *
 * // Accent focus ring (Braun Orange)
 * <Input accent placeholder="Accent focus" />
 *
 * // File input
 * <Input type="file" />
 * ```
 */
const Input = React.forwardRef<
    HTMLInputElement,
    React.ComponentProps<'input'> & { accent?: boolean }
>(({ className, accent, type, ...props }, ref) => {
    return (
        <input
            type={type}
            className={`drams-input ${accent ? 'accent' : ''} ${className || ''}`.trim()}
            ref={ref}
            {...props}
        />
    )
})
Input.displayName = 'Input'

/**
 * Textarea
 *
 * A multi-line text input component.
 * API matches shadcn/ui Textarea exactly.
 *
 * @see https://ui.shadcn.com/docs/components/textarea
 *
 * @example
 * ```tsx
 * <Textarea placeholder="Enter description..." />
 * <Textarea rows={5} />
 * <Textarea aria-invalid />
 * ```
 */
const Textarea = React.forwardRef<
    HTMLTextAreaElement,
    React.ComponentProps<'textarea'> & { accent?: boolean }
>(({ className, accent, ...props }, ref) => {
    return (
        <textarea
            className={`drams-input drams-textarea ${accent ? 'accent' : ''} ${className || ''}`.trim()}
            ref={ref}
            {...props}
        />
    )
})
Textarea.displayName = 'Textarea'

export { Input, Textarea }
