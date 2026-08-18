/**
 * Popover - DRAMS3
 *
 * Displays rich content in a portal, triggered by a button.
 *
 * Built on Radix UI Popover with shadcn-compatible API.
 *
 * @example
 * <Popover>
 *   <PopoverTrigger asChild>
 *     <Button variant="outline">Open</Button>
 *   </PopoverTrigger>
 *   <PopoverContent>
 *     Place content here.
 *   </PopoverContent>
 * </Popover>
 */

import * as React from 'react';
import * as PopoverPrimitive from '@radix-ui/react-popover';

/* ==========================================================================
   Root & Trigger
   ========================================================================== */

const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;
const PopoverAnchor = PopoverPrimitive.Anchor;
const PopoverPortal = PopoverPrimitive.Portal;

/* ==========================================================================
   Content
   ========================================================================== */

export interface PopoverContentProps
    extends React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content> {
    /**
     * The preferred alignment against the anchor.
     * @default "center"
     */
    align?: 'start' | 'center' | 'end';
    /**
     * The preferred side of the anchor to render against.
     * @default "bottom"
     */
    side?: 'top' | 'right' | 'bottom' | 'left';
    /**
     * The distance in pixels from the anchor.
     * @default 4
     */
    sideOffset?: number;
}

const PopoverContent = React.forwardRef<
    React.ComponentRef<typeof PopoverPrimitive.Content>,
    PopoverContentProps
>(({ className, align = 'center', sideOffset = 4, ...props }, ref) => (
    <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
            ref={ref}
            align={align}
            sideOffset={sideOffset}
            className={['drams-popover-content', className].filter(Boolean).join(' ')}
            {...props}
        />
    </PopoverPrimitive.Portal>
));

PopoverContent.displayName = PopoverPrimitive.Content.displayName;

/* ==========================================================================
   Close
   ========================================================================== */

const PopoverClose = PopoverPrimitive.Close;

/* ==========================================================================
   Exports
   ========================================================================== */

export {
    Popover,
    PopoverTrigger,
    PopoverContent,
    PopoverAnchor,
    PopoverPortal,
    PopoverClose,
};
