import * as React from 'react'

/* ═══════════════════════════════════════════════════════════════
   FORM
   Form container with proper structure.
   ═══════════════════════════════════════════════════════════════ */

export interface FormProps extends React.FormHTMLAttributes<HTMLFormElement> { }

export const Form = React.forwardRef<HTMLFormElement, FormProps>(
    ({ className, ...props }, ref) => {
        return (
            <form
                ref={ref}
                className={`drams-form ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Form.displayName = 'Form'

/* ═══════════════════════════════════════════════════════════════
   FORM FIELD
   Groups a label, control, and description together.
   ═══════════════════════════════════════════════════════════════ */

export interface FormFieldProps extends React.HTMLAttributes<HTMLDivElement> {
    /** Mark field as invalid */
    invalid?: boolean
}

export const FormField = React.forwardRef<HTMLDivElement, FormFieldProps>(
    ({ invalid, className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={`drams-form-field ${className || ''}`.trim()}
                data-invalid={invalid ? 'true' : undefined}
                {...props}
            />
        )
    }
)
FormField.displayName = 'FormField'

/* ═══════════════════════════════════════════════════════════════
   FORM DESCRIPTION
   Helper text below a form control.
   ═══════════════════════════════════════════════════════════════ */

export interface FormDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> { }

export const FormDescription = React.forwardRef<HTMLParagraphElement, FormDescriptionProps>(
    ({ className, ...props }, ref) => {
        return (
            <p
                ref={ref}
                className={`drams-form-description ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
FormDescription.displayName = 'FormDescription'

/* ═══════════════════════════════════════════════════════════════
   FORM MESSAGE
   Error or validation message for a form control.
   ═══════════════════════════════════════════════════════════════ */

export interface FormMessageProps extends React.HTMLAttributes<HTMLParagraphElement> {
    /** Message type */
    variant?: 'error' | 'success'
}

export const FormMessage = React.forwardRef<HTMLParagraphElement, FormMessageProps>(
    ({ variant = 'error', className, ...props }, ref) => {
        return (
            <p
                ref={ref}
                className={`drams-form-message ${className || ''}`.trim()}
                data-variant={variant}
                {...props}
            />
        )
    }
)
FormMessage.displayName = 'FormMessage'

/* ═══════════════════════════════════════════════════════════════
   FIELDSET
   Groups related form fields.
   ═══════════════════════════════════════════════════════════════ */

export interface FieldsetProps extends React.FieldsetHTMLAttributes<HTMLFieldSetElement> { }

export const Fieldset = React.forwardRef<HTMLFieldSetElement, FieldsetProps>(
    ({ className, ...props }, ref) => {
        return (
            <fieldset
                ref={ref}
                className={`drams-fieldset ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Fieldset.displayName = 'Fieldset'

/* ═══════════════════════════════════════════════════════════════
   LEGEND
   Caption for a fieldset.
   ═══════════════════════════════════════════════════════════════ */

export interface LegendProps extends React.HTMLAttributes<HTMLLegendElement> { }

export const Legend = React.forwardRef<HTMLLegendElement, LegendProps>(
    ({ className, ...props }, ref) => {
        return (
            <legend
                ref={ref}
                className={`drams-legend ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Legend.displayName = 'Legend'
