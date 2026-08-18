import * as React from 'react'
import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area'

/**
 * ScrollArea
 *
 * Custom scrollable area with styled scrollbars.
 * API matches shadcn/ui ScrollArea.
 *
 * @see https://ui.shadcn.com/docs/components/scroll-area
 *
 * @example
 * ```tsx
 * <ScrollArea className="h-[200px] w-[350px]">
 *   <div>Scrollable content...</div>
 * </ScrollArea>
 * ```
 */

export interface ScrollAreaProps
    extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root> {
    /** Thin scrollbars */
    thin?: boolean
    /** Auto-hide scrollbars */
    autoHide?: boolean
    /** Accent colored scrollbar */
    accent?: boolean
}

const ScrollArea = React.forwardRef<
    React.ComponentRef<typeof ScrollAreaPrimitive.Root>,
    ScrollAreaProps
>(({ className, thin, autoHide, accent, children, ...props }, ref) => {
    const thinClass = thin ? 'drams-scroll-area--thin' : ''
    const autoHideClass = autoHide ? 'drams-scroll-area--auto-hide' : ''
    const accentClass = accent ? 'accent' : ''

    return (
        <ScrollAreaPrimitive.Root
            ref={ref}
            className={`drams-scroll-area ${thinClass} ${autoHideClass} ${accentClass} ${className || ''}`.trim()}
            {...props}
        >
            <ScrollAreaPrimitive.Viewport className="drams-scroll-area-viewport">
                {children}
            </ScrollAreaPrimitive.Viewport>
            <ScrollBar />
            <ScrollBar orientation="horizontal" />
            <ScrollAreaPrimitive.Corner className="drams-scroll-area-corner" />
        </ScrollAreaPrimitive.Root>
    )
})
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName

/* ═══════════════════════════════════════════════════════════════
   SCROLL BAR
   Individual scrollbar component.
   ═══════════════════════════════════════════════════════════════ */

export interface ScrollBarProps
    extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar> { }

const ScrollBar = React.forwardRef<
    React.ComponentRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>,
    ScrollBarProps
>(({ className, orientation = 'vertical', ...props }, ref) => (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
        ref={ref}
        orientation={orientation}
        className={`drams-scrollbar ${className || ''}`.trim()}
        {...props}
    >
        <ScrollAreaPrimitive.ScrollAreaThumb className="drams-scrollbar-thumb" />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
))
ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName

export { ScrollArea, ScrollBar }
