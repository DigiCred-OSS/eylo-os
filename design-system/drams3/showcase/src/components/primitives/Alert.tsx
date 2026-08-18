/**
 * Alert - DRAMS3
 *
 * Displays a callout for user attention.
 *
 * shadcn-compatible API (no Radix dependency - HTML only).
 *
 * @example
 * <Alert>
 *   <AlertTitle>Heads up!</AlertTitle>
 *   <AlertDescription>
 *     You can add components to your app using the cli.
 *   </AlertDescription>
 * </Alert>
 *
 * @example
 * <Alert variant="destructive">
 *   <AlertTitle>Error</AlertTitle>
 *   <AlertDescription>
 *     Your session has expired. Please log in again.
 *   </AlertDescription>
 * </Alert>
 */

import * as React from 'react';

/* ==========================================================================
   Alert Root
   ========================================================================== */

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
    /**
     * The variant of the alert.
     * @default "default"
     */
    variant?: 'default' | 'destructive';
}

/**
 * Alert - Container for alert content.
 */
const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
    ({ className, variant = 'default', ...props }, ref) => (
        <div
            ref={ref}
            role="alert"
            data-variant={variant}
            className={['drams-alert', className].filter(Boolean).join(' ')}
            {...props}
        />
    )
);

Alert.displayName = 'Alert';

/* ==========================================================================
   Alert Title
   ========================================================================== */

const AlertTitle = React.forwardRef<
    HTMLHeadingElement,
    React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
    <h5
        ref={ref}
        className={['drams-alert-title', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertTitle.displayName = 'AlertTitle';

/* ==========================================================================
   Alert Description
   ========================================================================== */

const AlertDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-alert-description', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertDescription.displayName = 'AlertDescription';

/* ==========================================================================
   Alert Action
   ========================================================================== */

/**
 * AlertAction - Action element (e.g., button) in the alert.
 * Positioned absolutely in top-right by CSS.
 */
const AlertAction = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={['drams-alert-action', className].filter(Boolean).join(' ')}
        {...props}
    />
));

AlertAction.displayName = 'AlertAction';

/* ==========================================================================
   Exports
   ========================================================================== */

export { Alert, AlertTitle, AlertDescription, AlertAction };
