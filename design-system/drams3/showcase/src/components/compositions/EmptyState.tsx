import * as React from 'react';

export interface EmptyStateProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
    action?: React.ReactNode;
    description?: React.ReactNode;
    icon?: React.ComponentType<{ className?: string; size?: number }>;
    title: React.ReactNode;
}

/**
 * EmptyState
 *
 * A composition for blank-slate and no-results states.
 * Uses existing typography, spacing, and action primitives without
 * introducing new visual invariants.
 */
export const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
    ({ action, className = '', description, icon: Icon, title, ...props }, ref) => {
        return (
            <div
                ref={ref}
                data-composition="empty-state"
                className={className || undefined}
                {...props}
            >
                {Icon ? (
                    <div data-slot="icon">
                        <Icon className="drams-empty-state-icon" size={48} />
                    </div>
                ) : null}

                <div data-slot="content">
                    <div data-slot="title">{title}</div>
                    {description ? <div data-slot="description">{description}</div> : null}
                </div>

                {action ? <div data-slot="action">{action}</div> : null}
            </div>
        );
    }
);

EmptyState.displayName = 'EmptyState';
