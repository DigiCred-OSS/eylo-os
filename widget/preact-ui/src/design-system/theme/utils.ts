/**
 * Eylo Widget Theme System - Utilities
 *
 * Helper functions for color conversion, validation, and token manipulation
 */

import type { OKLCHColor } from "./types";

/**
 * Validate OKLCH color format
 * @param color OKLCH color string
 * @returns true if valid
 */
export function isValidOKLCH(color: string): boolean {
  // Match patterns like: "62% 0.25 264" or "62 0.25 264"
  const oklchPattern = /^(\d+(\.\d+)?%?\s+\d+(\.\d+)?\s+\d+(\.\d+)?)$/;
  return oklchPattern.test(color.trim());
}

/**
 * Convert hex color to OKLCH (approximate)
 * Note: This is a simplified conversion. For production, consider using a library like culori
 *
 * @param hex Hex color (e.g., "#3b82f6")
 * @returns OKLCH color string
 */
export function hexToOKLCH(hex: string): OKLCHColor {
  // Remove # if present
  hex = hex.replace("#", "");

  // Convert to RGB
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  // Simple sRGB to OKLCH approximation
  // For precise conversion, use a color library
  const lightness = (0.2126 * r + 0.7152 * g + 0.0722 * b) * 100;
  const chroma = Math.sqrt((r - 0.5) ** 2 + (g - 0.5) ** 2 + (b - 0.5) ** 2) * 0.4;
  const hue = Math.atan2(b - g, r - g) * (180 / Math.PI);

  return `${lightness.toFixed(1)}% ${chroma.toFixed(3)} ${(hue + 360) % 360}`;
}

/**
 * Adjust OKLCH lightness
 * @param color OKLCH color
 * @param amount Amount to adjust (-100 to 100)
 * @returns Adjusted OKLCH color
 */
export function adjustLightness(color: OKLCHColor, amount: number): OKLCHColor {
  const parts = color.trim().split(/\s+/);
  if (parts.length !== 3) return color;

  let lightness = parseFloat(parts[0]);
  lightness = Math.max(0, Math.min(100, lightness + amount));

  return `${lightness}% ${parts[1]} ${parts[2]}`;
}

/**
 * Create a foreground color that contrasts with background
 * Uses simple lightness inversion
 *
 * @param backgroundColor OKLCH background color
 * @returns OKLCH foreground color with good contrast
 */
export function generateForeground(backgroundColor: OKLCHColor): OKLCHColor {
  const parts = backgroundColor.trim().split(/\s+/);
  if (parts.length !== 3) return "0% 0 0"; // Fallback to black

  const lightness = parseFloat(parts[0]);
  const chroma = parts[1];
  const hue = parts[2];

  // If background is light (>50%), use dark foreground
  // If background is dark (<50%), use light foreground
  if (lightness > 50) {
    return `20.5% ${chroma} ${hue}`; // Dark
  } else {
    return `98.5% ${chroma} ${hue}`; // Light
  }
}

/**
 * Convert camelCase to kebab-case
 * @param str camelCase string
 * @returns kebab-case string
 */
export function camelToKebab(str: string): string {
  return str.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

/**
 * Convert camelCase property to CSS custom property name
 * @param property Property name (e.g., "primaryForeground")
 * @returns CSS variable name (e.g., "--ew-primary-foreground")
 */
export function toCSSVariable(property: string): string {
  return `--ew-${camelToKebab(property)}`;
}

/**
 * Parse CSS length value to numeric value (in pixels, assuming 16px = 1rem)
 * @param value CSS length value
 * @returns Numeric value in pixels
 */
export function parseLength(value: string): number {
  const match = value.match(/^([\d.]+)(rem|px|em)$/);
  if (!match) return 0;

  const [, num, unit] = match;
  const numValue = parseFloat(num);

  switch (unit) {
    case "rem":
    case "em":
      return numValue * 16; // Assume 16px base
    case "px":
      return numValue;
    default:
      return 0;
  }
}

/**
 * Validate CSS length value
 * @param value CSS length value
 * @returns true if valid
 */
export function isValidLength(value: string): boolean {
  return /^[\d.]+(rem|px|em|%)$/.test(value);
}

/**
 * Create a color scale from a base color
 * Generates 9 shades (50, 100, 200, ..., 900)
 *
 * @param baseColor OKLCH base color (typically 500 level)
 * @returns Object with color scale
 */
export function createColorScale(baseColor: OKLCHColor): Record<number, OKLCHColor> {
  const steps = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900];
  const adjustments = [45, 40, 30, 15, 5, 0, -10, -20, -30, -45];

  return steps.reduce(
    (scale, step, index) => {
      scale[step] = adjustLightness(baseColor, adjustments[index]);
      return scale;
    },
    {} as Record<number, OKLCHColor>
  );
}

/**
 * Merge theme objects (deep merge)
 * @param base Base theme
 * @param override Theme to merge on top
 * @returns Merged theme
 */
export function mergeThemes<T extends Record<string, any>>(base: T, override: Partial<T>): T {
  const result = { ...base } as T;

  for (const key in override) {
    const value = override[key];
    if (value !== undefined) {
      if (typeof value === "object" && !Array.isArray(value) && value !== null) {
        result[key] = mergeThemes(result[key] || ({} as any), value) as any;
      } else {
        result[key] = value as any;
      }
    }
  }

  return result;
}
