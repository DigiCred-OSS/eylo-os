import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Alert.module.css";

export interface AlertProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "destructive" | "success" | "warning" | "info";
  children?: ComponentChildren;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "default", children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="alert"
        className={cm(styles.alert, styles[variant], className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Alert.displayName = "Alert";

export const AlertTitle = forwardRef<
  HTMLHeadingElement,
  preact.JSX.HTMLAttributes<HTMLHeadingElement>
>(({ className, children, ...props }, ref) => {
  return (
    <h5 ref={ref} className={cm(styles.title, className)} {...props}>
      {children}
    </h5>
  );
});

AlertTitle.displayName = "AlertTitle";

export const AlertDescription = forwardRef<
  HTMLParagraphElement,
  preact.JSX.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  return (
    <div ref={ref} className={cm(styles.description, className)} {...props}>
      {children}
    </div>
  );
});

AlertDescription.displayName = "AlertDescription";
