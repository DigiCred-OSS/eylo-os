import { type ComponentChildren } from "preact";
import { cm } from "../utils";
import styles from "./Badge.module.css";

export interface BadgeProps extends preact.JSX.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
  children?: ComponentChildren;
}

export const Badge = ({ variant = "default", className, children, ...props }: BadgeProps) => {
  return (
    <span className={cm(styles.badge, styles[variant], className)} {...props}>
      {children}
    </span>
  );
};

Badge.displayName = "Badge";
