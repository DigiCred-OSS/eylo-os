import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Separator.module.css";

export interface SeparatorProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical";
  decorative?: boolean;
}

export const Separator = forwardRef<HTMLDivElement, SeparatorProps>(
  ({ className, orientation = "horizontal", decorative = true, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role={decorative ? "none" : "separator"}
        aria-orientation={orientation}
        className={cm(styles.separator, styles[orientation], className)}
        {...props}
      />
    );
  }
);

Separator.displayName = "Separator";
