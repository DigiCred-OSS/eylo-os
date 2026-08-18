import * as React from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { CheckIcon, ChevronRightIcon, CircleIcon } from 'lucide-react'

/**
 * DropdownMenu
 *
 * Dropdown menu with physical surface appearance.
 * API matches shadcn/ui DropdownMenu exactly.
 *
 * @see https://ui.shadcn.com/docs/components/dropdown-menu
 *
 * @example
 * ```tsx
 * <DropdownMenu>
 *   <DropdownMenuTrigger asChild>
 *     <Button variant="outline">Open</Button>
 *   </DropdownMenuTrigger>
 *   <DropdownMenuContent>
 *     <DropdownMenuLabel>My Account</DropdownMenuLabel>
 *     <DropdownMenuSeparator />
 *     <DropdownMenuItem>Profile</DropdownMenuItem>
 *     <DropdownMenuItem>Settings</DropdownMenuItem>
 *     <DropdownMenuSeparator />
 *     <DropdownMenuItem variant="destructive">Log out</DropdownMenuItem>
 *   </DropdownMenuContent>
 * </DropdownMenu>
 * ```
 */
const DropdownMenu = DropdownMenuPrimitive.Root

const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger

const DropdownMenuGroup = DropdownMenuPrimitive.Group

const DropdownMenuPortal = DropdownMenuPrimitive.Portal

const DropdownMenuSub = DropdownMenuPrimitive.Sub

const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup

/**
 * DropdownMenuSubTrigger
 */
export interface DropdownMenuSubTriggerProps
    extends React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubTrigger> {
    inset?: boolean
}

const DropdownMenuSubTrigger = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.SubTrigger>,
    DropdownMenuSubTriggerProps
>(({ className = '', inset, children, ...props }, ref) => (
    <DropdownMenuPrimitive.SubTrigger
        ref={ref}
        className={`drams-dropdown-item drams-dropdown-subtrigger ${inset ? 'data-[inset]' : ''} ${className}`.trim()}
        {...props}
    >
        {children}
        <ChevronRightIcon className="drams-dropdown-subtrigger-icon" />
    </DropdownMenuPrimitive.SubTrigger>
))
DropdownMenuSubTrigger.displayName = DropdownMenuPrimitive.SubTrigger.displayName

/**
 * DropdownMenuSubContent
 */
const DropdownMenuSubContent = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.SubContent>,
    React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubContent>
>(({ className = '', ...props }, ref) => (
    <DropdownMenuPrimitive.SubContent
        ref={ref}
        className={`drams-dropdown-subcontent ${className}`.trim()}
        {...props}
    />
))
DropdownMenuSubContent.displayName = DropdownMenuPrimitive.SubContent.displayName

/**
 * DropdownMenuContent
 */
export interface DropdownMenuContentProps
    extends React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content> {
    /**
     * Distance from trigger
     */
    sideOffset?: number
}

const DropdownMenuContent = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.Content>,
    DropdownMenuContentProps
>(({ className = '', sideOffset = 4, ...props }, ref) => (
    <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
            ref={ref}
            sideOffset={sideOffset}
            className={`drams-dropdown-content ${className}`.trim()}
            {...props}
        />
    </DropdownMenuPrimitive.Portal>
))
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName

/**
 * DropdownMenuItem
 */
export interface DropdownMenuItemProps
    extends React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> {
    /**
     * Inset item (aligns with items that have indicators)
     */
    inset?: boolean

    /**
     * Variant
     * - default: Normal item
     * - destructive: For dangerous actions
     */
    variant?: 'default' | 'destructive'
}

const DropdownMenuItem = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.Item>,
    DropdownMenuItemProps
>(({ className = '', inset, variant = 'default', ...props }, ref) => {
    const dataAttrs: Record<string, string | boolean> = {}
    if (variant !== 'default') {
        dataAttrs['data-variant'] = variant
    }
    if (inset) {
        dataAttrs['data-inset'] = true
    }

    return (
        <DropdownMenuPrimitive.Item
            ref={ref}
            className={`drams-dropdown-item ${className}`.trim()}
            {...dataAttrs}
            {...props}
        />
    )
})
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName

/**
 * DropdownMenuCheckboxItem
 */
const DropdownMenuCheckboxItem = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.CheckboxItem>,
    React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.CheckboxItem> & {
        accent?: boolean
    }
>(({ className = '', accent, children, checked, ...props }, ref) => (
    <DropdownMenuPrimitive.CheckboxItem
        ref={ref}
        className={`drams-dropdown-item ${accent ? 'accent' : ''} ${className}`.trim()}
        data-has-indicator
        checked={checked}
        {...props}
    >
        <span className="drams-dropdown-item-indicator">
            <DropdownMenuPrimitive.ItemIndicator>
                <CheckIcon size={16} />
            </DropdownMenuPrimitive.ItemIndicator>
        </span>
        {children}
    </DropdownMenuPrimitive.CheckboxItem>
))
DropdownMenuCheckboxItem.displayName = DropdownMenuPrimitive.CheckboxItem.displayName

/**
 * DropdownMenuRadioItem
 */
const DropdownMenuRadioItem = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.RadioItem>,
    React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.RadioItem> & {
        accent?: boolean
    }
>(({ className = '', accent, children, ...props }, ref) => (
    <DropdownMenuPrimitive.RadioItem
        ref={ref}
        className={`drams-dropdown-item ${accent ? 'accent' : ''} ${className}`.trim()}
        data-has-indicator
        {...props}
    >
        <span className="drams-dropdown-item-indicator">
            <DropdownMenuPrimitive.ItemIndicator>
                <CircleIcon size={8} fill="currentColor" />
            </DropdownMenuPrimitive.ItemIndicator>
        </span>
        {children}
    </DropdownMenuPrimitive.RadioItem>
))
DropdownMenuRadioItem.displayName = DropdownMenuPrimitive.RadioItem.displayName

/**
 * DropdownMenuLabel
 */
export interface DropdownMenuLabelProps
    extends React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Label> {
    inset?: boolean
}

const DropdownMenuLabel = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.Label>,
    DropdownMenuLabelProps
>(({ className = '', inset, ...props }, ref) => (
    <DropdownMenuPrimitive.Label
        ref={ref}
        className={`drams-dropdown-label ${className}`.trim()}
        data-inset={inset || undefined}
        {...props}
    />
))
DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName

/**
 * DropdownMenuSeparator
 */
const DropdownMenuSeparator = React.forwardRef<
    React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
    React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className = '', ...props }, ref) => (
    <DropdownMenuPrimitive.Separator
        ref={ref}
        className={`drams-dropdown-separator ${className}`.trim()}
        {...props}
    />
))
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName

/**
 * DropdownMenuShortcut
 *
 * Keyboard shortcut hint display.
 */
const DropdownMenuShortcut = ({
    className = '',
    ...props
}: React.HTMLAttributes<HTMLSpanElement>) => {
    return (
        <span
            className={`drams-dropdown-shortcut ${className}`.trim()}
            {...props}
        />
    )
}
DropdownMenuShortcut.displayName = 'DropdownMenuShortcut'

export {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuCheckboxItem,
    DropdownMenuRadioItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuShortcut,
    DropdownMenuGroup,
    DropdownMenuPortal,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuRadioGroup,
}
