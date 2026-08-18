import * as React from 'react'
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'

/**
 * RadioGroup
 *
 * A set of checkable buttons where no more than one can be checked at a time.
 * API matches shadcn/ui RadioGroup exactly.
 *
 * @see https://ui.shadcn.com/docs/components/radio-group
 *
 * @example
 * ```tsx
 * <RadioGroup defaultValue="option-one">
 *   <div className="flex items-center gap-3">
 *     <RadioGroupItem value="option-one" id="option-one" />
 *     <Label htmlFor="option-one">Option One</Label>
 *   </div>
 *   <div className="flex items-center gap-3">
 *     <RadioGroupItem value="option-two" id="option-two" />
 *     <Label htmlFor="option-two">Option Two</Label>
 *   </div>
 * </RadioGroup>
 * ```
 */
const RadioGroup = React.forwardRef<
    React.ComponentRef<typeof RadioGroupPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>
>(({ className, ...props }, ref) => {
    return (
        <RadioGroupPrimitive.Root
            className={`drams-radio-group ${className || ''}`.trim()}
            {...props}
            ref={ref}
        />
    )
})
RadioGroup.displayName = RadioGroupPrimitive.Root.displayName

/**
 * RadioGroupItem
 *
 * Individual radio button within a RadioGroup.
 * Dot indicator appears ONLY when selected.
 * Default: black indicator. With accent prop: Braun Orange.
 */
const RadioGroupItem = React.forwardRef<
    React.ComponentRef<typeof RadioGroupPrimitive.Item>,
    React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item> & { accent?: boolean }
>(({ className, accent, ...props }, ref) => {
    return (
        <RadioGroupPrimitive.Item
            ref={ref}
            className={`drams-radio ${accent ? 'accent' : ''} ${className || ''}`.trim()}
            {...props}
        >
            <RadioGroupPrimitive.Indicator className="drams-radio-indicator" />
        </RadioGroupPrimitive.Item>
    )
})
RadioGroupItem.displayName = RadioGroupPrimitive.Item.displayName

export { RadioGroup, RadioGroupItem }
