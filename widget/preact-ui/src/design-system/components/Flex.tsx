/**
 * Flex Component
 *
 * A layout primitive for flexbox layouts with semantic props.
 * For simple vertical/horizontal stacking, prefer Stack component.
 *
 * @example
 * <Flex align="center" justify="between" gap="md">
 *   <div>Left</div>
 *   <div>Right</div>
 * </Flex>
 */

import { type ComponentChildren } from "preact";
import styles from "./Flex.module.css";

type Spacing = "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
type Align = "start" | "center" | "end" | "stretch" | "baseline";
type Justify = "start" | "center" | "end" | "between" | "around" | "evenly";
type Direction = "row" | "column" | "row-reverse" | "column-reverse";
type Wrap = "nowrap" | "wrap" | "wrap-reverse";
type Size = "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "full";

export interface FlexProps {
  children: ComponentChildren;
  gap?: Spacing;
  align?: Align;
  justify?: Justify;
  direction?: Direction;
  wrap?: Wrap;
  grow?: boolean;
  height?: Size;
  width?: Size;
  border?: boolean;
  borderRadius?: "sm" | "md" | "lg" | "xl" | "full";
  shadow?: "xs" | "sm" | "md" | "lg" | "xl" | "none";
  className?: string;
}

export function Flex({
  children,
  gap,
  align,
  justify,
  direction = "row",
  wrap = "nowrap",
  grow,
  height,
  width,
  border,
  borderRadius,
  shadow,
  className = "",
}: FlexProps) {
  const classes = [
    styles.flex,
    gap && styles[`gap-${gap}`],
    align && styles[`align-${align}`],
    justify && styles[`justify-${justify}`],
    styles[`direction-${direction}`],
    styles[`wrap-${wrap}`],
    grow && styles.grow,
    height && styles[`height-${height}`],
    width && styles[`width-${width}`],
    border && styles.border,
    borderRadius && styles[`radius-${borderRadius}`],
    shadow && styles[`shadow-${shadow}`],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <div className={classes}>{children}</div>;
}
