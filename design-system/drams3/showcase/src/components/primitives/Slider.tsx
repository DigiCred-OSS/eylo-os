import * as React from 'react'
import * as SliderPrimitive from '@radix-ui/react-slider'

/**
 * Slider
 *
 * Range input slider.
 * API matches shadcn/ui Slider.
 *
 * @see https://ui.shadcn.com/docs/components/slider
 *
 * @example
 * ```tsx
 * <Slider defaultValue={[33]} max={100} step={1} />
 * <Slider defaultValue={[25, 75]} max={100} step={1} /> // Range
 * ```
 */

export interface SliderProps
    extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
    /** Accent color variant */
    accent?: boolean
}

const Slider = React.forwardRef<
    React.ComponentRef<typeof SliderPrimitive.Root>,
    SliderProps
>(({ className, accent, defaultValue, value, ...props }, ref) => {
    const accentClass = accent ? 'drams-slider--accent' : ''
    const thumbCount = value?.length ?? defaultValue?.length ?? 1

    return (
        <SliderPrimitive.Root
            ref={ref}
            className={`drams-slider ${accentClass} ${className || ''}`.trim()}
            defaultValue={defaultValue}
            value={value}
            {...props}
        >
            <SliderPrimitive.Track className="drams-slider-track">
                <SliderPrimitive.Range className="drams-slider-range" />
            </SliderPrimitive.Track>
            {Array.from({ length: thumbCount }).map((_, i) => (
                <SliderPrimitive.Thumb key={i} className="drams-slider-thumb" />
            ))}
        </SliderPrimitive.Root>
    )
})
Slider.displayName = SliderPrimitive.Root.displayName

export { Slider }
