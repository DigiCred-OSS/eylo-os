/**
 * Alert Dialog - DRAMS3
 *
 * A modal dialog that interrupts the user with important content and expects
 * a response. Use for destructive actions or important confirmations.
 *
 * Built on Radix UI AlertDialog with shadcn-compatible API.
 *
 * @example
 * <AlertDialog>
 *   <AlertDialogTrigger asChild>
 *     <Button variant="destructive">Delete</Button>
 *   </AlertDialogTrigger>
 *   <AlertDialogContent>
 *     <AlertDialogHeader>
 *       <AlertDialogTitle>Are you sure?</AlertDialogTitle>
 *       <AlertDialogDescription>
 *         This action cannot be undone.
 *       </AlertDialogDescription>
 *     </AlertDialogHeader>
 *     <AlertDialogFooter>
 *       <AlertDialogCancel>Cancel</AlertDialogCancel>
 *       <AlertDialogAction>Continue</AlertDialogAction>
 *     </AlertDialogFooter>
 *   </AlertDialogContent>
 * </AlertDialog>
 */

import * as React from 'react';
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog';

/* ==========================================================================
   Root & Trigger
   ========================================================================== */

const AlertDialog = AlertDialogPrimitive.Root;
const AlertDialogTrigger = AlertDialogPrimitive.Trigger;
const AlertDialogPortal = AlertDialogPrimitive.Portal;

/* ==========================================================================
   Overlay (Backdrop)
   ========================================================================== */

const AlertDialogOverlay = React.forwardRef<
    React.ComponentRef<typeof AlertDialogPrimitive.Overlay>,
    React.ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
    <AlertDialogPrimitive.Overlay
        ref={ref}
        className={['drams-dialog-overlay', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDialogOverlay.displayName = AlertDialogPrimitive.Overlay.displayName;

/* ==========================================================================
   Content
   ========================================================================== */

const AlertDialogContent = React.forwardRef<
    React.ComponentRef<typeof AlertDialogPrimitive.Content>,
    React.ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
    <AlertDialogPortal>
        <AlertDialogOverlay />
        <AlertDialogPrimitive.Content
            ref={ref}
            className={['drams-dialog-content', 'drams-alert-dialog-content', className].filter(Boolean).join(' ')}
            {...props}
        >
            {children}
        </AlertDialogPrimitive.Content>
    </AlertDialogPortal>
));

AlertDialogContent.displayName = AlertDialogPrimitive.Content.displayName;

/* ==========================================================================
   Header
   ========================================================================== */

const AlertDialogHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-dialog-header', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDialogHeader.displayName = 'AlertDialogHeader';

/* ==========================================================================
   Footer
   ========================================================================== */

const AlertDialogFooter = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-dialog-footer', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDialogFooter.displayName = 'AlertDialogFooter';

/* ==========================================================================
   Title
   ========================================================================== */

const AlertDialogTitle = React.forwardRef<
    React.ComponentRef<typeof AlertDialogPrimitive.Title>,
    React.ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Title>
>(({ className, ...props }, ref) => (
    <AlertDialogPrimitive.Title
        ref={ref}
        className={['drams-dialog-title', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDialogTitle.displayName = AlertDialogPrimitive.Title.displayName;

/* ==========================================================================
   Description
   ========================================================================== */

const AlertDialogDescription = React.forwardRef<
    React.ComponentRef<typeof AlertDialogPrimitive.Description>,
    React.ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Description>
>(({ className, ...props }, ref) => (
    <AlertDialogPrimitive.Description
        ref={ref}
        className={['drams-dialog-description', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDialogDescription.displayName = AlertDialogPrimitive.Description.displayName;

/* ==========================================================================
   Action & Cancel Buttons
   ========================================================================== */

const AlertDialogAction = React.forwardRef<
    React.ComponentRef<typeof AlertDialogPrimitive.Action>,
    React.ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Action>
>(({ className, ...props }, ref) => (
    <AlertDialogPrimitive.Action
        ref={ref}
        className={['drams-button', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDialogAction.displayName = AlertDialogPrimitive.Action.displayName;

const AlertDialogCancel = React.forwardRef<
    React.ComponentRef<typeof AlertDialogPrimitive.Cancel>,
    React.ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Cancel>
>(({ className, ...props }, ref) => (
    <AlertDialogPrimitive.Cancel
        ref={ref}
        className={['drams-button', className].filter(Boolean).join(' ')}
        data-variant="outline"
        {...props}
    />
));

AlertDialogCancel.displayName = AlertDialogPrimitive.Cancel.displayName;

/* ==========================================================================
   Exports
   ========================================================================== */

export {
    AlertDialog,
    AlertDialogPortal,
    AlertDialogOverlay,
    AlertDialogTrigger,
    AlertDialogContent,
    AlertDialogHeader,
    AlertDialogFooter,
    AlertDialogTitle,
    AlertDialogDescription,
    AlertDialogAction,
    AlertDialogCancel,
};
