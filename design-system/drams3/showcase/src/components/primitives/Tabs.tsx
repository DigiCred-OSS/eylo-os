/**
 * Tabs - DRAMS3
 *
 * A set of layered sections of content—known as tab panels—that are
 * displayed one at a time.
 *
 * Built on Radix UI Tabs with shadcn-compatible API.
 *
 * @example
 * <Tabs defaultValue="account">
 *   <TabsList>
 *     <TabsTrigger value="account">Account</TabsTrigger>
 *     <TabsTrigger value="password">Password</TabsTrigger>
 *   </TabsList>
 *   <TabsContent value="account">Account content</TabsContent>
 *   <TabsContent value="password">Password content</TabsContent>
 * </Tabs>
 */

import * as React from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';

/* ==========================================================================
   Root
   ========================================================================== */

export interface TabsProps
    extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.Root> {
    /**
     * The orientation of the tabs.
     * @default "horizontal"
     */
    orientation?: 'horizontal' | 'vertical';
}

/**
 * Tabs root component. Contains all tabs parts.
 */
const Tabs = React.forwardRef<
    React.ComponentRef<typeof TabsPrimitive.Root>,
    TabsProps
>(({ className, orientation = 'horizontal', ...props }, ref) => (
    <TabsPrimitive.Root
        ref={ref}
        orientation={orientation}
        data-orientation={orientation}
        className={['drams-tabs', className].filter(Boolean).join(' ')}
        {...props}
    />
));

Tabs.displayName = TabsPrimitive.Root.displayName;

/* ==========================================================================
   List
   ========================================================================== */

export interface TabsListProps
    extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.List> {
    /**
     * The visual style variant.
     * @default "default"
     */
    variant?: 'default' | 'line';

    /**
     * Render the selected tab in the brand.
     *
     * Composes with `variant` rather than replacing it — an accented line
     * tab list is still a line tab list.
     */
    accent?: boolean;
}

/**
 * TabsList - Container for tab triggers.
 */
const TabsList = React.forwardRef<
    React.ComponentRef<typeof TabsPrimitive.List>,
    TabsListProps
>(({ className, variant = 'default', accent, ...props }, ref) => (
    <TabsPrimitive.List
        ref={ref}
        data-variant={variant}
        className={['drams-tabs-list', accent && 'accent', className].filter(Boolean).join(' ')}
        {...props}
    />
));

TabsList.displayName = TabsPrimitive.List.displayName;

/* ==========================================================================
   Trigger
   ========================================================================== */

export interface TabsTriggerProps
    extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger> { }

/**
 * TabsTrigger - A button that activates its associated content.
 */
const TabsTrigger = React.forwardRef<
    React.ComponentRef<typeof TabsPrimitive.Trigger>,
    TabsTriggerProps
>(({ className, ...props }, ref) => (
    <TabsPrimitive.Trigger
        ref={ref}
        className={['drams-tabs-trigger', className].filter(Boolean).join(' ')}
        {...props}
    />
));

TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

/* ==========================================================================
   Breadcrumb Tabs Composition Helpers
   ========================================================================== */

export interface BreadcrumbTabsListProps
    extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.List> { }

const BreadcrumbTabsList = React.forwardRef<
    React.ComponentRef<typeof TabsPrimitive.List>,
    BreadcrumbTabsListProps
>(({ className, ...props }, ref) => (
    <TabsPrimitive.List
        ref={ref}
        className={['drams-breadcrumb-tabs-list', className].filter(Boolean).join(' ')}
        {...props}
    />
));

BreadcrumbTabsList.displayName = 'BreadcrumbTabsList';

export interface BreadcrumbTabsTriggerProps
    extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger> { }

const BreadcrumbTabsTrigger = React.forwardRef<
    React.ComponentRef<typeof TabsPrimitive.Trigger>,
    BreadcrumbTabsTriggerProps
>(({ className, ...props }, ref) => (
    <TabsPrimitive.Trigger
        ref={ref}
        className={['drams-breadcrumb-tabs-trigger', className].filter(Boolean).join(' ')}
        {...props}
    />
));

BreadcrumbTabsTrigger.displayName = 'BreadcrumbTabsTrigger';

export interface BreadcrumbTabsSeparatorProps
    extends React.ComponentPropsWithoutRef<'div'> { }

const BreadcrumbTabsSeparator = React.forwardRef<HTMLDivElement, BreadcrumbTabsSeparatorProps>(
    ({ children = '|', className, ...props }, ref) => (
        <div
            ref={ref}
            aria-hidden="true"
            className={['drams-breadcrumb-tabs-separator', className].filter(Boolean).join(' ')}
            {...props}
        >
            {children}
        </div>
    )
);

BreadcrumbTabsSeparator.displayName = 'BreadcrumbTabsSeparator';

/* ==========================================================================
   Content
   ========================================================================== */

export interface TabsContentProps
    extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content> { }

/**
 * TabsContent - The content associated with each trigger.
 */
const TabsContent = React.forwardRef<
    React.ComponentRef<typeof TabsPrimitive.Content>,
    TabsContentProps
>(({ className, ...props }, ref) => (
    <TabsPrimitive.Content
        ref={ref}
        className={['drams-tabs-content', className].filter(Boolean).join(' ')}
        {...props}
    />
));

TabsContent.displayName = TabsPrimitive.Content.displayName;

/* ==========================================================================
   Exports
   ========================================================================== */

export {
    BreadcrumbTabsList,
    BreadcrumbTabsSeparator,
    BreadcrumbTabsTrigger,
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger
};
