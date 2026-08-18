import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./List.module.css";

export interface ListProps extends preact.JSX.HTMLAttributes<HTMLUListElement> {
  children?: ComponentChildren;
  variant?: "default" | "compact" | "relaxed";
}

export const List = forwardRef<HTMLUListElement, ListProps>(
  ({ className, children, variant = "default", ...props }, ref) => {
    return (
      <ul
        ref={ref}
        className={cm(
          styles.list,
          variant === "compact" && styles.listCompact,
          variant === "relaxed" && styles.listRelaxed,
          className
        )}
        {...props}
      >
        {children}
      </ul>
    );
  }
);

List.displayName = "List";

export interface ListItemProps extends preact.JSX.HTMLAttributes<HTMLLIElement> {
  icon?: ComponentChildren;
  label?: string;
  description?: string;
  action?: ComponentChildren;
  active?: boolean;
  disabled?: boolean;
  variant?: "default" | "compact" | "relaxed";
  children?: ComponentChildren;
}

export const ListItem = forwardRef<HTMLLIElement, ListItemProps>(
  (
    {
      className,
      icon,
      label,
      description,
      action,
      active,
      disabled,
      variant = "default",
      children,
      ...props
    },
    ref
  ) => {
    return (
      <li
        ref={ref}
        className={cm(
          styles.item,
          variant === "compact" && styles.itemCompact,
          variant === "relaxed" && styles.itemRelaxed,
          active && styles.itemActive,
          disabled && styles.itemDisabled,
          className
        )}
        {...props}
      >
        {icon && <div className={styles.itemIcon}>{icon}</div>}
        {(label || description) && (
          <div className={styles.itemContent}>
            {label && <div className={styles.itemLabel}>{label}</div>}
            {description && <div className={styles.itemDescription}>{description}</div>}
          </div>
        )}
        {children}
        {action && <div className={styles.itemAction}>{action}</div>}
      </li>
    );
  }
);

ListItem.displayName = "ListItem";

export const ListDivider = forwardRef<HTMLHRElement, preact.JSX.HTMLAttributes<HTMLHRElement>>(
  ({ className, ...props }, ref) => {
    return <hr ref={ref} className={cm(styles.divider, className)} {...props} />;
  }
);

ListDivider.displayName = "ListDivider";
