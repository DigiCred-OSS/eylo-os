/**
 * Link Component
 *
 * A semantic link component with consistent styling and accessibility.
 * Handles internal and external links with proper security attributes.
 *
 * @example
 * <Link href="/path">Internal link</Link>
 * <Link href="https://example.com" external>External link</Link>
 * <Link variant="primary" bold>Styled link</Link>
 */

import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import styles from "./Link.module.css";

type Variant = "default" | "muted" | "primary" | "destructive" | "success" | "warning";
type Size = "xs" | "sm" | "base" | "lg" | "xl";

export interface LinkProps extends preact.JSX.HTMLAttributes<HTMLAnchorElement> {
  children: ComponentChildren;
  href: string;
  /** Link color variant */
  variant?: Variant;
  /** Text size */
  size?: Size;
  /** Bold text */
  bold?: boolean;
  /** Semibold text */
  semibold?: boolean;
  /** Show underline (default: on hover only) */
  underline?: "none" | "hover" | "always";
  /** External link - opens in new tab with security attributes */
  external?: boolean;
  /** Disabled state - link is not clickable */
  disabled?: boolean;
  className?: string;
}

export const Link = forwardRef<HTMLAnchorElement, LinkProps>(
  (
    {
      children,
      href,
      variant = "default",
      size = "base",
      bold = false,
      semibold = false,
      underline = "hover",
      external = false,
      disabled = false,
      className = "",
      onClick,
      ...props
    },
    ref
  ) => {
    const classes = [
      styles.link,
      styles[`size-${size}`],
      variant !== "default" && styles[`variant-${variant}`],
      bold && styles.bold,
      semibold && styles.semibold,
      styles[`underline-${underline}`],
      disabled && styles.disabled,
      className,
    ]
      .filter(Boolean)
      .join(" ");

    const handleClick = (e: MouseEvent) => {
      if (disabled) {
        e.preventDefault();
        return;
      }
      onClick?.(e as any);
    };

    // External links should open in new tab with security attributes
    const externalProps = external
      ? {
          target: "_blank",
          rel: "noopener noreferrer",
        }
      : {};

    return (
      <a
        ref={ref}
        href={disabled ? undefined : href}
        className={classes}
        onClick={handleClick}
        aria-disabled={disabled}
        {...externalProps}
        {...props}
      >
        {children}
      </a>
    );
  }
);

Link.displayName = "Link";
