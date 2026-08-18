import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'

/**
 * ButtonGroup component props
 *
 * COMPOSITION: ButtonGroup is not a primitive — it's Flex + Button.
 * This React wrapper provides API compatibility with shadcn/ui.
 *
 * @see /compositions/button-group.md
 */
export interface ButtonGroupProps extends React.HTMLAttributes<HTMLDivElement> {
    /**
     * The orientation of the button group.
     * @default "horizontal"
     */
    orientation?: 'horizontal' | 'vertical'
}

/**
 * ButtonGroup
 *
 * A composition that groups related buttons together.
 * Buttons within a group have their border-radii adjusted to create a
 * connected appearance.
 *
 * This is a COMPOSITION, not a primitive. It introduces no new invariants.
 *
 * @example
 * ```tsx
 * <ButtonGroup>
 *   <Button>Button 1</Button>
 *   <Button>Button 2</Button>
 * </ButtonGroup>
 *
 * <ButtonGroup orientation="vertical">
 *   <Button>Top</Button>
 *   <Button>Bottom</Button>
 * </ButtonGroup>
 * ```
 */
export const ButtonGroup = React.forwardRef<HTMLDivElement, ButtonGroupProps>(
    ({ orientation = 'horizontal', className = '', children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                role="group"
                data-composition="button-group"
                data-orientation={orientation !== 'horizontal' ? orientation : undefined}
                className={className || undefined}
                {...props}
            >
                {children}
            </div>
        )
    }
)
ButtonGroup.displayName = 'ButtonGroup'

/**
 * ButtonGroupSeparator component props
 */
export interface ButtonGroupSeparatorProps extends React.HTMLAttributes<HTMLDivElement> {
    /**
     * The orientation of the separator.
     * Use "vertical" (default) for horizontal button groups.
     * Use "horizontal" for vertical button groups.
     * @default "vertical"
     */
    orientation?: 'horizontal' | 'vertical'
}

/**
 * ButtonGroupSeparator
 *
 * A visual divider between buttons within a group.
 * Buttons with variant="outline" don't need separators since they have borders.
 *
 * @example
 * ```tsx
 * <ButtonGroup>
 *   <Button>Save</Button>
 *   <ButtonGroupSeparator />
 *   <Button size="icon"><ChevronDown /></Button>
 * </ButtonGroup>
 * ```
 */
export const ButtonGroupSeparator = React.forwardRef<HTMLDivElement, ButtonGroupSeparatorProps>(
    ({ orientation = 'vertical', className = '', ...props }, ref) => {
        return (
            <div
                ref={ref}
                role="separator"
                aria-orientation={orientation}
                data-slot="separator"
                data-orientation={orientation !== 'vertical' ? orientation : undefined}
                className={className || undefined}
                {...props}
            />
        )
    }
)
ButtonGroupSeparator.displayName = 'ButtonGroupSeparator'

/**
 * ButtonGroupText component props
 */
export interface ButtonGroupTextProps extends React.HTMLAttributes<HTMLSpanElement> {
    /**
     * Change the default rendered element to the one passed as a child,
     * merging their props and behavior.
     *
     * @example
     * ```tsx
     * <ButtonGroupText asChild>
     *   <Label htmlFor="name">Name</Label>
     * </ButtonGroupText>
     * ```
     */
    asChild?: boolean
}

/**
 * ButtonGroupText
 *
 * Display text within a button group. Use for labels or static text
 * that should align with the buttons.
 *
 * @example
 * ```tsx
 * <ButtonGroup>
 *   <ButtonGroupText>Label:</ButtonGroupText>
 *   <Input placeholder="Value" />
 *   <Button>Submit</Button>
 * </ButtonGroup>
 *
 * // With asChild for custom elements
 * <ButtonGroup>
 *   <ButtonGroupText asChild>
 *     <Label htmlFor="input">Name</Label>
 *   </ButtonGroupText>
 *   <Input id="input" />
 * </ButtonGroup>
 * ```
 */
export const ButtonGroupText = React.forwardRef<HTMLSpanElement, ButtonGroupTextProps>(
    ({ asChild = false, className = '', children, ...props }, ref) => {
        const Comp = asChild ? Slot : 'span'

        return (
            <Comp
                ref={ref}
                data-slot="text"
                className={className || undefined}
                {...props}
            >
                {children}
            </Comp>
        )
    }
)
ButtonGroupText.displayName = 'ButtonGroupText'
