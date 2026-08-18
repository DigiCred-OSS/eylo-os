import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'

/**
 * Select
 *
 * A dropdown menu for selecting from a list of options.
 * API matches shadcn/ui Select exactly.
 *
 * @see https://ui.shadcn.com/docs/components/select
 *
 * @example
 * ```tsx
 * <Select>
 *   <SelectTrigger>
 *     <SelectValue placeholder="Select a fruit" />
 *   </SelectTrigger>
 *   <SelectContent>
 *     <SelectItem value="apple">Apple</SelectItem>
 *     <SelectItem value="banana">Banana</SelectItem>
 *     <SelectItem value="cherry">Cherry</SelectItem>
 *   </SelectContent>
 * </Select>
 * ```
 */
const Select = SelectPrimitive.Root

const SelectGroup = SelectPrimitive.Group

const SelectValue = SelectPrimitive.Value

/* ═══════════════════════════════════════════════════════════════
   SELECT TRIGGER
   ═══════════════════════════════════════════════════════════════ */

export interface SelectTriggerProps
    extends React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger> {
    /** Accent variant for focus ring */
    accent?: boolean
}

const SelectTrigger = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.Trigger>,
    SelectTriggerProps
>(({ className, accent, children, ...props }, ref) => (
    <SelectPrimitive.Trigger
        ref={ref}
        className={`drams-select-trigger ${accent ? 'accent' : ''} ${className || ''}`.trim()}
        {...props}
    >
        <span className="drams-select-value" style={{ flex: 1, textAlign: 'left' }}>
            {children}
        </span>
        <SelectPrimitive.Icon asChild>
            <ChevronDownIcon className="drams-select-icon" />
        </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
))
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName

/* ═══════════════════════════════════════════════════════════════
   SELECT CONTENT
   ═══════════════════════════════════════════════════════════════ */

export interface SelectContentProps
    extends React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content> {
    /** Position of the content relative to trigger */
    position?: 'item-aligned' | 'popper'
}

const SelectContent = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.Content>,
    SelectContentProps
>(({ className, children, position = 'popper', sideOffset = 4, ...props }, ref) => (
    <SelectPrimitive.Portal>
        <SelectPrimitive.Content
            ref={ref}
            className={`drams-select-content ${className || ''}`.trim()}
            position={position}
            sideOffset={sideOffset}
            {...props}
        >
            <SelectScrollUpButton />
            <SelectPrimitive.Viewport
                className={`drams-select-viewport ${position === 'popper' ? 'drams-select-viewport--popper' : ''}`.trim()}
            >
                {children}
            </SelectPrimitive.Viewport>
            <SelectScrollDownButton />
        </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
))
SelectContent.displayName = SelectPrimitive.Content.displayName

/* ═══════════════════════════════════════════════════════════════
   SELECT ITEM
   ═══════════════════════════════════════════════════════════════ */

export interface SelectItemProps
    extends React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item> {
    /** Accent variant for indicator */
    accent?: boolean
}

const SelectItem = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.Item>,
    SelectItemProps
>(({ className, accent, children, ...props }, ref) => (
    <SelectPrimitive.Item
        ref={ref}
        className={`drams-select-item ${accent ? 'accent' : ''} ${className || ''}`.trim()}
        {...props}
    >
        <SelectPrimitive.ItemIndicator className="drams-select-item-indicator">
            <CheckIcon />
        </SelectPrimitive.ItemIndicator>
        <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
))
SelectItem.displayName = SelectPrimitive.Item.displayName

/* ═══════════════════════════════════════════════════════════════
   SELECT LABEL
   ═══════════════════════════════════════════════════════════════ */

const SelectLabel = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.Label>,
    React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...props }, ref) => (
    <SelectPrimitive.Label
        ref={ref}
        className={`drams-select-label ${className || ''}`.trim()}
        {...props}
    />
))
SelectLabel.displayName = SelectPrimitive.Label.displayName

/* ═══════════════════════════════════════════════════════════════
   SELECT SEPARATOR
   ═══════════════════════════════════════════════════════════════ */

const SelectSeparator = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.Separator>,
    React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ className, ...props }, ref) => (
    <SelectPrimitive.Separator
        ref={ref}
        className={`drams-select-separator ${className || ''}`.trim()}
        {...props}
    />
))
SelectSeparator.displayName = SelectPrimitive.Separator.displayName

/* ═══════════════════════════════════════════════════════════════
   SCROLL BUTTONS
   ═══════════════════════════════════════════════════════════════ */

const SelectScrollUpButton = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.ScrollUpButton>,
    React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollUpButton>
>(({ className, ...props }, ref) => (
    <SelectPrimitive.ScrollUpButton
        ref={ref}
        className={`drams-select-scroll-button ${className || ''}`.trim()}
        {...props}
    >
        <ChevronUpIcon />
    </SelectPrimitive.ScrollUpButton>
))
SelectScrollUpButton.displayName = SelectPrimitive.ScrollUpButton.displayName

const SelectScrollDownButton = React.forwardRef<
    React.ComponentRef<typeof SelectPrimitive.ScrollDownButton>,
    React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollDownButton>
>(({ className, ...props }, ref) => (
    <SelectPrimitive.ScrollDownButton
        ref={ref}
        className={`drams-select-scroll-button ${className || ''}`.trim()}
        {...props}
    >
        <ChevronDownIcon />
    </SelectPrimitive.ScrollDownButton>
))
SelectScrollDownButton.displayName = SelectPrimitive.ScrollDownButton.displayName

/* ═══════════════════════════════════════════════════════════════
   ICONS (inline SVG for zero dependencies)
   ═══════════════════════════════════════════════════════════════ */

function ChevronDownIcon({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <path
                d="M4 6L8 10L12 6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    )
}

function ChevronUpIcon({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <path
                d="M12 10L8 6L4 10"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    )
}

function CheckIcon({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <path
                d="M13.5 4.5L6.5 11.5L3 8"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    )
}

export {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectLabel,
    SelectScrollDownButton,
    SelectScrollUpButton,
    SelectSeparator,
    SelectTrigger,
    SelectValue,
}
