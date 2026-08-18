import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Card.module.css";

export interface CardProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  children?: ComponentChildren;
  /** Visual variant */
  variant?: "default" | "muted" | "bordered";
  /** Border */
  border?: boolean;
  /** Border radius */
  borderRadius?: "sm" | "md" | "lg" | "xl" | "full" | "none";
  /** Shadow */
  shadow?: "xs" | "sm" | "md" | "lg" | "xl" | "none";
  /** Padding */
  padding?: "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
  /** Interactive styles (cursor pointer, transition, hover lift) */
  interactive?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      className,
      children,
      variant = "default",
      border,
      borderRadius,
      shadow,
      padding,
      interactive,
      ...props
    },
    ref
  ) => {
    return (
      <div
        ref={ref}
        className={cm(
          styles.card,
          variant !== "default" && styles[`variant-${variant}`],
          border && styles.border,
          borderRadius && styles[`radius-${borderRadius}`],
          shadow && styles[`shadow-${shadow}`],
          padding && styles[`padding-${padding}`],
          interactive && styles.interactive,
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.header, className)} {...props}>
        {children}
      </div>
    );
  }
);

CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLDivElement, preact.JSX.HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.title, className)} {...props}>
        {children}
      </div>
    );
  }
);

CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<
  HTMLDivElement,
  preact.JSX.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  return (
    <div ref={ref} className={cm(styles.description, className)} {...props}>
      {children}
    </div>
  );
});

CardDescription.displayName = "CardDescription";

export const CardAction = forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.action, className)} {...props}>
        {children}
      </div>
    );
  }
);

CardAction.displayName = "CardAction";

export const CardContent = forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.content, className)} {...props}>
        {children}
      </div>
    );
  }
);

CardContent.displayName = "CardContent";

export const CardFooter = forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.footer, className)} {...props}>
        {children}
      </div>
    );
  }
);

CardFooter.displayName = "CardFooter";
