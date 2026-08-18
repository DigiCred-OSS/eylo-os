/**
 * Tooltip - DRAMS3
 *
 * A popup that displays information related to an element when the element
 * receives keyboard focus or the mouse hovers over it.
 *
 * Built on Radix UI Tooltip with shadcn-compatible API.
 *
 * @example
 * <TooltipProvider>
 *   <Tooltip>
 *     <TooltipTrigger>Hover me</TooltipTrigger>
 *     <TooltipContent>Tooltip text</TooltipContent>
 *   </Tooltip>
 * </TooltipProvider>
 */

import * as React from 'react';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';

/* ==========================================================================
   Provider
   ========================================================================== */

/**
 * TooltipProvider wraps your app to provide shared tooltip configuration.
 * Typically placed at the root of your app.
 */
const TooltipProvider = TooltipPrimitive.Provider;

/* ==========================================================================
   Root
   ========================================================================== */

/**
 * Tooltip root component. Contains all tooltip parts.
 */
const Tooltip = TooltipPrimitive.Root;

/* ==========================================================================
   Trigger
   ========================================================================== */

/**
 * TooltipTrigger - The element that triggers the tooltip.
 * Wraps the element that should show the tooltip on hover/focus.
 */
const TooltipTrigger = TooltipPrimitive.Trigger;

/* ==========================================================================
   Content
   ========================================================================== */

export interface TooltipContentProps
    extends React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content> {
    /**
     * The preferred side of the trigger to render against.
     * @default "top"
     */
    side?: 'top' | 'right' | 'bottom' | 'left';
    /**
     * The distance in pixels from the trigger.
     * @default 4
     */
    sideOffset?: number;
}

/**
 * TooltipContent - The content that appears when the tooltip is open.
 */
const TooltipContent = React.forwardRef<
    React.ComponentRef<typeof TooltipPrimitive.Content>,
    TooltipContentProps
>(({ className, sideOffset = 4, children, ...props }, ref) => (
    <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
            ref={ref}
            sideOffset={sideOffset}
            className={['drams-tooltip-content', className].filter(Boolean).join(' ')}
            {...props}
        >
            {children}
        </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
));

TooltipContent.displayName = TooltipPrimitive.Content.displayName;

/* ==========================================================================
   Exports
   ========================================================================== */

export {
    Tooltip,
    TooltipTrigger,
    TooltipContent,
    TooltipProvider,
};
