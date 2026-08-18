import { forwardRef } from "preact/compat";
import type { ComponentChildren } from "preact";
import { cm } from "../utils";
import styles from "./Label.module.css";

export interface LabelProps extends preact.JSX.HTMLAttributes<HTMLLabelElement> {
  error?: boolean;
  children?: ComponentChildren;
}

export const Label = forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, error, children, ...props }, ref) => {
    return (
      <label ref={ref} className={cm(styles.label, error && styles.error, className)} {...props}>
        {children}
      </label>
    );
  }
);

Label.displayName = "Label";
