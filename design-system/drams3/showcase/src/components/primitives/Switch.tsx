import * as React from 'react'
import * as SwitchPrimitive from '@radix-ui/react-switch'

/**
 * Switch
 *
 * A control that allows the user to toggle between checked and not checked.
 * API matches shadcn/ui Switch exactly.
 *
 * @see https://ui.shadcn.com/docs/components/switch
 *
 * @example
 * ```tsx
 * // Basic
 * <Switch />
 *
 * // Controlled
 * const [checked, setChecked] = React.useState(false)
 * <Switch checked={checked} onCheckedChange={setChecked} />
 *
 * // With label
 * <label className="drams-switch-label">
 *   <Switch />
 *   <span>Airplane Mode</span>
 * </label>
 *
 * // Accent variant (Braun Orange when ON)
 * <Switch accent />
 *
 * // Disabled
 * <Switch disabled />
 * ```
 */
const Switch = React.forwardRef<
    React.ComponentRef<typeof SwitchPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root> & { accent?: boolean }
>(({ className, accent, ...props }, ref) => (
    <SwitchPrimitive.Root
        className={`drams-switch ${accent ? 'accent' : ''} ${className || ''}`.trim()}
        {...props}
        ref={ref}
    >
        <SwitchPrimitive.Thumb className="drams-switch-thumb" />
    </SwitchPrimitive.Root>
))
Switch.displayName = SwitchPrimitive.Root.displayName

export { Switch }
