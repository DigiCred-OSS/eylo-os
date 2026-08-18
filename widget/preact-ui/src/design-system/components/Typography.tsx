import { forwardRef } from "preact/compat";
import type { ComponentChildren } from "preact";
import { cm } from "../utils";
import styles from "./Typography.module.css";

// Heading component
export interface HeadingProps extends preact.JSX.HTMLAttributes<HTMLHeadingElement> {
  as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
  variant?: "default" | "muted" | "destructive" | "success" | "warning";
  children?: ComponentChildren;
}

export const Heading = forwardRef<HTMLHeadingElement, HeadingProps>(
  ({ as: Component = "h2", variant = "default", className, children, ...props }, ref) => {
    return (
      <Component
        ref={ref as any}
        className={cm(
          styles.heading,
          styles[Component],
          variant !== "default" && styles[`variant-${variant}`],
          className
        )}
        {...props}
      >
        {children}
      </Component>
    );
  }
);

Heading.displayName = "Heading";

// Text component
export interface TextProps extends preact.JSX.HTMLAttributes<HTMLElement> {
  as?: "p" | "span" | "div" | "label";
  size?: "large" | "base" | "small" | "xs";
  variant?: "default" | "muted" | "subtle" | "destructive" | "success" | "warning";
  bold?: boolean;
  semibold?: boolean;
  uppercase?: boolean;
  truncate?: boolean;
  /** Text alignment */
  align?: "left" | "center" | "right";
  // Deprecated: use variant="muted" instead
  muted?: boolean;
  // Deprecated: use variant="subtle" instead
  subtle?: boolean;
  children?: ComponentChildren;
}

export const Text = forwardRef<HTMLElement, TextProps>(
  (
    {
      as: Component = "p",
      size = "base",
      variant = "default",
      bold = false,
      semibold = false,
      uppercase = false,
      truncate = false,
      align,
      // Backwards compatibility
      muted = false,
      subtle = false,
      className,
      children,
      ...props
    },
    ref
  ) => {
    // Handle backwards compatibility: muted/subtle props override variant
    const effectiveVariant = muted ? "muted" : subtle ? "subtle" : variant;

    return (
      <Component
        ref={ref as any}
        className={cm(
          styles.text,
          styles[size],
          effectiveVariant !== "default" && styles[`variant-${effectiveVariant}`],
          bold && styles.bold,
          semibold && styles.semibold,
          uppercase && styles.uppercase,
          truncate && styles.truncate,
          align && styles[`align-${align}`],
          className
        )}
        {...props}
      >
        {children}
      </Component>
    );
  }
);

Text.displayName = "Text";

// Label component - for section headers, form labels
export interface LabelProps extends preact.JSX.HTMLAttributes<HTMLElement> {
  as?: "label" | "div" | "span";
  variant?: "default" | "muted" | "destructive" | "success" | "warning";
  htmlFor?: string;
  children?: ComponentChildren;
}

export const Label = forwardRef<HTMLElement, LabelProps>(
  ({ as: Component = "label", variant = "muted", className, children, ...props }, ref) => {
    return (
      <Component
        ref={ref as any}
        className={cm(
          styles.label,
          variant !== "default" && styles[`variant-${variant}`],
          className
        )}
        {...props}
      >
        {children}
      </Component>
    );
  }
);

Label.displayName = "Label";

// Code component
export interface CodeProps extends preact.JSX.HTMLAttributes<HTMLElement> {
  children?: ComponentChildren;
}

export const Code = forwardRef<HTMLElement, CodeProps>(({ className, children, ...props }, ref) => {
  return (
    <code ref={ref as any} className={cm(styles.code, className)} {...props}>
      {children}
    </code>
  );
});

Code.displayName = "Code";
