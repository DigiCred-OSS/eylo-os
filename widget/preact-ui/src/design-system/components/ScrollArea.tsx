import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./ScrollArea.module.css";

export interface ScrollAreaProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  children?: ComponentChildren;
}

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.scrollArea, className)} {...props}>
        <div className={styles.viewport}>{children}</div>
      </div>
    );
  }
);

ScrollArea.displayName = "ScrollArea";
