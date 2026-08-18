import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Skeleton.module.css";

export interface SkeletonProps extends Omit<preact.JSX.HTMLAttributes<HTMLDivElement>, "height"> {
  /** Height using design tokens */
  height?: "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
  /** Width style (full = 100%) */
  width?: "full";
}

export const Skeleton = forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, height, width, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cm(
          styles.skeleton,
          height && styles[`height-${height}`],
          width === "full" && styles.widthFull,
          className
        )}
        {...props}
      />
    );
  }
);

Skeleton.displayName = "Skeleton";
