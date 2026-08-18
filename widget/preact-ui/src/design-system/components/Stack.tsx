/**
 * Stack Component
 *
 * A layout primitive for vertical or horizontal stacking with consistent spacing.
 * Replaces manual flex + gap utility combinations.
 *
 * @example
 * <Stack spacing="md">
 *   <Card>Item 1</Card>
 *   <Card>Item 2</Card>
 * </Stack>
 */

import { type ComponentChildren } from "preact";
import styles from "./Stack.module.css";

type Spacing = "none" | "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
type Direction = "vertical" | "horizontal";
type Align = "start" | "center" | "end" | "stretch";

export interface StackProps {
  children: ComponentChildren;
  spacing?: Spacing;
  direction?: Direction;
  align?: Align;
  border?: boolean;
  borderRadius?: "sm" | "md" | "lg" | "xl" | "full";
  shadow?: "xs" | "sm" | "md" | "lg" | "xl" | "none";
  className?: string;
}

export function Stack({
  children,
  spacing = "none",
  direction = "vertical",
  align,
  border,
  borderRadius,
  shadow,
  className = "",
}: StackProps) {
  const classes = [
    styles.stack,
    styles[`spacing-${spacing}`],
    styles[`direction-${direction}`],
    align && styles[`align-${align}`],
    border && styles.border,
    borderRadius && styles[`radius-${borderRadius}`],
    shadow && styles[`shadow-${shadow}`],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <div className={classes}>{children}</div>;
}
