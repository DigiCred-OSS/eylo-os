/**
 * Class name utility for conditional and merged class names
 * Lightweight alternative to clsx/classnames
 */

export type ClassValue =
  | string
  | number
  | boolean
  | undefined
  | null
  | ClassValue[]
  | { [key: string]: any };

export function cn(...inputs: ClassValue[]): string {
  return inputs
    .flat()
    .filter((x) => typeof x === "string" && x.length > 0)
    .join(" ")
    .trim();
}

/**
 * Compose multiple class names with CSS module styles
 * Usage: cm(styles.base, isActive && styles.active, className)
 */
export function cm(...classes: ClassValue[]): string {
  return cn(...classes);
}
