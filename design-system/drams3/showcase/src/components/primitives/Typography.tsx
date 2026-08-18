import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'

/* ═══════════════════════════════════════════════════════════════
   HEADING
   Semantic heading elements (h1-h4).
   ═══════════════════════════════════════════════════════════════ */

export interface HeadingProps extends React.HTMLAttributes<HTMLHeadingElement> {
    /** Heading level (1-4) */
    level?: 1 | 2 | 3 | 4
    /** Render as child element */
    asChild?: boolean
}

export const Heading = React.forwardRef<HTMLHeadingElement, HeadingProps>(
    ({ level = 2, asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : (`h${level}` as const)
        return (
            <Comp
                ref={ref}
                className={`drams-h${level} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Heading.displayName = 'Heading'

/* ═══════════════════════════════════════════════════════════════
   TEXT
   Body text with size and color variants.
   ═══════════════════════════════════════════════════════════════ */

export interface TextProps extends React.HTMLAttributes<HTMLParagraphElement> {
    /** Text size */
    size?: 'sm' | 'default' | 'lg'
    /** Text color */
    color?: 'default' | 'secondary' | 'muted'
    /** Render as child element or specific element */
    as?: 'p' | 'span' | 'div'
    /** Render as child element */
    asChild?: boolean
}

export const Text = React.forwardRef<HTMLParagraphElement, TextProps>(
    ({ size = 'default', color = 'default', as = 'p', asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : as
        const modifiers = [
            size !== 'default' && `drams-text--${size}`,
            color !== 'default' && `drams-text--${color}`,
        ].filter(Boolean).join(' ')

        return (
            <Comp
                ref={ref}
                className={`drams-text ${modifiers} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Text.displayName = 'Text'

/* ═══════════════════════════════════════════════════════════════
   CAPTION
   Small helper text for descriptions, hints, etc.
   ═══════════════════════════════════════════════════════════════ */

export interface CaptionProps extends React.HTMLAttributes<HTMLSpanElement> {
    /** Render as child element */
    asChild?: boolean
}

export const Caption = React.forwardRef<HTMLSpanElement, CaptionProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'span'
        return (
            <Comp
                ref={ref}
                className={`drams-caption ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Caption.displayName = 'Caption'

/* ═══════════════════════════════════════════════════════════════
   CODE
   Inline code text.
   ═══════════════════════════════════════════════════════════════ */

export interface CodeProps extends React.HTMLAttributes<HTMLElement> {
    /** Render as child element */
    asChild?: boolean
}

export const Code = React.forwardRef<HTMLElement, CodeProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'code'
        return (
            <Comp
                ref={ref}
                className={`drams-code ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Code.displayName = 'Code'
