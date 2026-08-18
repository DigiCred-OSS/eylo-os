/**
 * Box Component
 *
 * A flexible container primitive with design token-based styling.
 * Replaces manual padding, margin, and border utility combinations.
 *
 * @example
 * <Box padding="md" borderRadius="lg">
 *   Content
 * </Box>
 */

import { type ComponentChildren } from "preact";
import styles from "./Box.module.css";

type Spacing = "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
type Radius = "sm" | "md" | "lg" | "xl" | "full";
type Display = "block" | "flex" | "inline-flex" | "grid" | "inline-block";
type Size = "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "full";
type Background =
  | "muted"
  | "muted-subtle"
  | "primary"
  | "secondary"
  | "destructive"
  | "success"
  | "warning";
type Color =
  | "default"
  | "muted"
  | "primary"
  | "primary-foreground"
  | "destructive"
  | "success"
  | "warning";

export interface BoxProps {
  children: ComponentChildren;
  padding?: Spacing;
  paddingX?: Spacing;
  paddingY?: Spacing;
  margin?: Spacing;
  marginTop?: Spacing;
  marginBottom?: Spacing;
  borderRadius?: Radius;
  display?: Display;
  background?: Background;
  height?: Size;
  width?: Size;
  border?: boolean;
  shadow?: "xs" | "sm" | "md" | "lg" | "xl" | "none";
  color?: Color;
  className?: string;
  onClick?: () => void;
}

export function Box({
  children,
  padding,
  paddingX,
  paddingY,
  margin,
  marginTop,
  marginBottom,
  borderRadius,
  display = "block",
  background,
  height,
  width,
  border,
  shadow,
  color,
  className = "",
  onClick,
}: BoxProps) {
  const classes = [
    styles.box,
    display && styles[`display-${display}`],
    padding && styles[`padding-${padding}`],
    paddingX && styles[`padding-x-${paddingX}`],
    paddingY && styles[`padding-y-${paddingY}`],
    margin && styles[`margin-${margin}`],
    marginTop && styles[`margin-top-${marginTop}`],
    marginBottom && styles[`margin-bottom-${marginBottom}`],
    borderRadius && styles[`radius-${borderRadius}`],
    background && styles[`bg-${background}`],
    height && styles[`height-${height}`],
    width && styles[`width-${width}`],
    border && styles.border,
    shadow && styles[`shadow-${shadow}`],
    color && styles[`color-${color}`],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} onClick={onClick}>
      {children}
    </div>
  );
}
