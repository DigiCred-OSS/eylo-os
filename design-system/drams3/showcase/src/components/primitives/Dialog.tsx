/**
 * Dialog - DRAMS3
 *
 * A window overlaid on either the primary window or another dialog window,
 * rendering the content underneath inert.
 *
 * Built on Radix UI Dialog with shadcn-compatible API.
 *
 * @example
 * <Dialog>
 *   <DialogTrigger asChild>
 *     <Button>Open Dialog</Button>
 *   </DialogTrigger>
 *   <DialogContent>
 *     <DialogHeader>
 *       <DialogTitle>Title</DialogTitle>
 *       <DialogDescription>Description</DialogDescription>
 *     </DialogHeader>
 *     <DialogFooter>
 *       <Button>Save</Button>
 *     </DialogFooter>
 *   </DialogContent>
 * </Dialog>
 */

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';

/* ==========================================================================
   Root & Trigger
   ========================================================================== */

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;
const DialogClose = DialogPrimitive.Close;

/* ==========================================================================
   Overlay (Backdrop)
   ========================================================================== */

const DialogOverlay = React.forwardRef<
    React.ComponentRef<typeof DialogPrimitive.Overlay>,
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Overlay
        ref={ref}
        className={['drams-dialog-overlay', className].filter(Boolean).join(' ')}
        {...props}
    />
));

DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

/* ==========================================================================
   Content
   ========================================================================== */

export interface DialogContentProps
    extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
    /**
     * Size of the dialog
     * @default "default"
     */
    size?: 'sm' | 'default' | 'lg' | 'xl' | 'full';
}

const DialogContent = React.forwardRef<
    React.ComponentRef<typeof DialogPrimitive.Content>,
    DialogContentProps
>(({ className, size = 'default', children, ...props }, ref) => (
    <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
            ref={ref}
            data-size={size}
            className={['drams-dialog-content', className].filter(Boolean).join(' ')}
            {...props}
        >
            {children}
            <DialogPrimitive.Close className="drams-dialog-close">
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
            </DialogPrimitive.Close>
        </DialogPrimitive.Content>
    </DialogPortal>
));

DialogContent.displayName = DialogPrimitive.Content.displayName;

/* ==========================================================================
   Header
   ========================================================================== */

const DialogHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-dialog-header', className].filter(Boolean).join(' ')}
        {...props}
    />
));

DialogHeader.displayName = 'DialogHeader';

/* ==========================================================================
   Footer
   ========================================================================== */

const DialogFooter = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-dialog-footer', className].filter(Boolean).join(' ')}
        {...props}
    />
));

DialogFooter.displayName = 'DialogFooter';

/* ==========================================================================
   Title
   ========================================================================== */

const DialogTitle = React.forwardRef<
    React.ComponentRef<typeof DialogPrimitive.Title>,
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Title
        ref={ref}
        className={['drams-dialog-title', className].filter(Boolean).join(' ')}
        {...props}
    />
));

DialogTitle.displayName = DialogPrimitive.Title.displayName;

/* ==========================================================================
   Description
   ========================================================================== */

const DialogDescription = React.forwardRef<
    React.ComponentRef<typeof DialogPrimitive.Description>,
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Description
        ref={ref}
        className={['drams-dialog-description', className].filter(Boolean).join(' ')}
        {...props}
    />
));

DialogDescription.displayName = DialogPrimitive.Description.displayName;

/* ==========================================================================
   Exports
   ========================================================================== */

export {
    Dialog,
    DialogPortal,
    DialogOverlay,
    DialogTrigger,
    DialogClose,
    DialogContent,
    DialogHeader,
    DialogFooter,
    DialogTitle,
    DialogDescription,
};
