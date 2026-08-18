/**
 * Sheet - DRAMS3
 *
 * COMPOSITION: A Dialog variant that slides in from the edge of the screen.
 * Extends the Dialog primitive with edge-based positioning.
 *
 * Uses Radix UI Dialog directly (not our Dialog primitive) because:
 * 1. Sheet has its own CSS class namespace (.drams-sheet-*)
 * 2. Animation behavior differs (slide vs scale)
 * 3. Side positioning via data-side attribute
 *
 * shadcn-compatible API.
 *
 * @example
 * <Sheet>
 *   <SheetTrigger asChild>
 *     <Button variant="outline">Open</Button>
 *   </SheetTrigger>
 *   <SheetContent>
 *     <SheetHeader>
 *       <SheetTitle>Edit Profile</SheetTitle>
 *       <SheetDescription>Make changes to your profile here.</SheetDescription>
 *     </SheetHeader>
 *   </SheetContent>
 * </Sheet>
 */

import * as React from 'react';
import * as SheetPrimitive from '@radix-ui/react-dialog';

/* ==========================================================================
   Root & Trigger
   ========================================================================== */

const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;
const SheetPortal = SheetPrimitive.Portal;

/* ==========================================================================
   Overlay (Backdrop)
   ========================================================================== */

const SheetOverlay = React.forwardRef<
    React.ComponentRef<typeof SheetPrimitive.Overlay>,
    React.ComponentPropsWithoutRef<typeof SheetPrimitive.Overlay>
>(({ className, ...props }, ref) => (
    <SheetPrimitive.Overlay
        ref={ref}
        className={['drams-sheet-overlay', className].filter(Boolean).join(' ')}
        {...props}
    />
));

SheetOverlay.displayName = SheetPrimitive.Overlay.displayName;

/* ==========================================================================
   Content
   ========================================================================== */

export interface SheetContentProps
    extends React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content> {
    /**
     * The side of the screen where the sheet appears.
     * @default "right"
     */
    side?: 'top' | 'right' | 'bottom' | 'left';
}

const SheetContent = React.forwardRef<
    React.ComponentRef<typeof SheetPrimitive.Content>,
    SheetContentProps
>(({ className, side = 'right', children, ...props }, ref) => (
    <SheetPortal>
        <SheetOverlay />
        <SheetPrimitive.Content
            ref={ref}
            data-side={side}
            className={['drams-sheet-content', className].filter(Boolean).join(' ')}
            {...props}
        >
            <SheetPrimitive.Close className="drams-sheet-close">
                <svg
                    width="15"
                    height="15"
                    viewBox="0 0 15 15"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <path
                        d="M11.7816 4.03157C12.0062 3.80702 12.0062 3.44295 11.7816 3.2184C11.5571 2.99385 11.193 2.99385 10.9685 3.2184L7.50005 6.68682L4.03164 3.2184C3.80708 2.99385 3.44301 2.99385 3.21846 3.2184C2.99391 3.44295 2.99391 3.80702 3.21846 4.03157L6.68688 7.49999L3.21846 10.9684C2.99391 11.193 2.99391 11.557 3.21846 11.7816C3.44301 12.0061 3.80708 12.0061 4.03164 11.7816L7.50005 8.31316L10.9685 11.7816C11.193 12.0061 11.5571 12.0061 11.7816 11.7816C12.0062 11.557 12.0062 11.193 11.7816 10.9684L8.31322 7.49999L11.7816 4.03157Z"
                        fill="currentColor"
                        fillRule="evenodd"
                        clipRule="evenodd"
                    />
                </svg>
                <span className="sr-only">Close</span>
            </SheetPrimitive.Close>
            {children}
        </SheetPrimitive.Content>
    </SheetPortal>
));

SheetContent.displayName = SheetPrimitive.Content.displayName;

/* ==========================================================================
   Header
   ========================================================================== */

const SheetHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-sheet-header', className].filter(Boolean).join(' ')}
        {...props}
    />
));

SheetHeader.displayName = 'SheetHeader';

/* ==========================================================================
   Footer
   ========================================================================== */

const SheetFooter = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-sheet-footer', className].filter(Boolean).join(' ')}
        {...props}
    />
));

SheetFooter.displayName = 'SheetFooter';

/* ==========================================================================
   Title
   ========================================================================== */

const SheetTitle = React.forwardRef<
    React.ComponentRef<typeof SheetPrimitive.Title>,
    React.ComponentPropsWithoutRef<typeof SheetPrimitive.Title>
>(({ className, ...props }, ref) => (
    <SheetPrimitive.Title
        ref={ref}
        className={['drams-sheet-title', className].filter(Boolean).join(' ')}
        {...props}
    />
));

SheetTitle.displayName = SheetPrimitive.Title.displayName;

/* ==========================================================================
   Description
   ========================================================================== */

const SheetDescription = React.forwardRef<
    React.ComponentRef<typeof SheetPrimitive.Description>,
    React.ComponentPropsWithoutRef<typeof SheetPrimitive.Description>
>(({ className, ...props }, ref) => (
    <SheetPrimitive.Description
        ref={ref}
        className={['drams-sheet-description', className].filter(Boolean).join(' ')}
        {...props}
    />
));

SheetDescription.displayName = SheetPrimitive.Description.displayName;

/* ==========================================================================
   Exports
   ========================================================================== */

export {
    Sheet,
    SheetPortal,
    SheetOverlay,
    SheetTrigger,
    SheetClose,
    SheetContent,
    SheetHeader,
    SheetFooter,
    SheetTitle,
    SheetDescription,
};
