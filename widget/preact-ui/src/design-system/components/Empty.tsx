import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Empty.module.css";

export interface EmptyProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  icon?: ComponentChildren;
  title?: string;
  description?: string;
  action?: ComponentChildren;
  children?: ComponentChildren;
}

export const Empty = forwardRef<HTMLDivElement, EmptyProps>(
  ({ className, icon, title, description, action, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.empty, className)} {...props}>
        {icon && <div className={styles.icon}>{icon}</div>}
        {title && <h3 className={styles.title}>{title}</h3>}
        {description && <p className={styles.description}>{description}</p>}
        {action && <div className={styles.action}>{action}</div>}
        {children}
      </div>
    );
  }
);

Empty.displayName = "Empty";
