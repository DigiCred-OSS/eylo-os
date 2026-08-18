/**
 * Eylo Widget Theme System - Theme Builder
 *
 * Fluent API for building themes programmatically
 */

import type {
  ColorTokens,
  EyloTheme,
  RadiusTokens,
  SpacingTokens,
  TypographyTokens,
} from "./types";
import { generateForeground } from "./utils";

/**
 * Fluent theme builder
 *
 * @example
 * const theme = createThemeBuilder()
 *   .setColors({ primary: '62% 0.25 264' })
 *   .setFontFamily('Inter', 'sans-serif')
 *   .setBaseRadius('0.75rem')
 *   .build();
 */
export class ThemeBuilder {
  private theme: EyloTheme = {};

  /**
   * Set color tokens
   */
  setColors(colors: Partial<ColorTokens>): this {
    this.theme.colors = { ...this.theme.colors, ...colors };
    return this;
  }

  /**
   * Set primary color and auto-generate foreground
   */
  setPrimaryColor(color: string, autoForeground = true): this {
    this.theme.colors = this.theme.colors || {};
    this.theme.colors.primary = color;

    if (autoForeground) {
      this.theme.colors.primaryForeground = generateForeground(color);
    }

    return this;
  }

  /**
   * Set destructive color and auto-generate foreground
   */
  setDestructiveColor(color: string, autoForeground = true): this {
    this.theme.colors = this.theme.colors || {};
    this.theme.colors.destructive = color;

    if (autoForeground) {
      this.theme.colors.destructiveForeground = generateForeground(color);
    }

    return this;
  }

  /**
   * Set success color and auto-generate foreground
   */
  setSuccessColor(color: string, autoForeground = true): this {
    this.theme.colors = this.theme.colors || {};
    this.theme.colors.success = color;

    if (autoForeground) {
      this.theme.colors.successForeground = generateForeground(color);
    }

    return this;
  }

  /**
   * Set background color and auto-generate foreground
   */
  setBackgroundColor(color: string, autoForeground = true): this {
    this.theme.colors = this.theme.colors || {};
    this.theme.colors.background = color;

    if (autoForeground) {
      this.theme.colors.foreground = generateForeground(color);
    }

    return this;
  }

  /**
   * Set font family
   */
  setFontFamily(family: string, type: "sans" | "mono" = "sans"): this {
    this.theme.typography = this.theme.typography || {};

    if (type === "sans") {
      this.theme.typography.fontSans = family;
    } else {
      this.theme.typography.fontMono = family;
    }

    return this;
  }

  /**
   * Set typography scale
   */
  setTypographyScale(scale: Partial<TypographyTokens>): this {
    this.theme.typography = { ...this.theme.typography, ...scale };
    return this;
  }

  /**
   * Set base font size (affects entire type scale proportionally)
   */
  setBaseFontSize(size: string): this {
    this.theme.typography = this.theme.typography || {};
    this.theme.typography.text = size; // Base font size
    return this;
  }

  /**
   * Set font weights
   */
  setFontWeights(weights: {
    normal?: number;
    medium?: number;
    semibold?: number;
    bold?: number;
  }): this {
    this.theme.typography = this.theme.typography || {};

    if (weights.normal) this.theme.typography.fontNormal = weights.normal;
    if (weights.medium) this.theme.typography.fontMedium = weights.medium;
    if (weights.semibold) this.theme.typography.fontSemibold = weights.semibold;
    if (weights.bold) this.theme.typography.fontBold = weights.bold;

    return this;
  }

  /**
   * Set spacing scale
   */
  setSpacingScale(scale: Partial<SpacingTokens>): this {
    this.theme.spacing = { ...this.theme.spacing, ...scale };
    return this;
  }

  /**
   * Set base spacing unit (affects entire spacing scale proportionally)
   */
  setBaseSpacing(unit: string): this {
    this.theme.spacing = this.theme.spacing || {};
    this.theme.spacing.spacing = unit; // Base spacing (1rem)
    return this;
  }

  /**
   * Set base radius and auto-calculate variants
   */
  setBaseRadius(radius: string): this {
    this.theme.radius = this.theme.radius || {};
    this.theme.radius.radius = radius;
    return this;
  }

  /**
   * Set all radius values
   */
  setRadiusScale(scale: Partial<RadiusTokens>): this {
    this.theme.radius = { ...this.theme.radius, ...scale };
    return this;
  }

  /**
   * Set shadow intensity (light, medium, heavy)
   */
  setShadowIntensity(intensity: "light" | "medium" | "heavy"): this {
    this.theme.shadows = this.theme.shadows || {};

    const intensityMap = {
      light: {
        shadowSm: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        shadow: "0 1px 3px 0 rgba(0, 0, 0, 0.06)",
        shadowMd: "0 2px 4px 0 rgba(0, 0, 0, 0.06)",
        shadowLg: "0 4px 6px 0 rgba(0, 0, 0, 0.06)",
        shadowXl: "0 8px 10px 0 rgba(0, 0, 0, 0.06)",
      },
      medium: {
        shadowSm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        shadow: "0 1px 3px 0 rgba(0, 0, 0, 0.10)",
        shadowMd: "0 4px 6px -1px rgba(0, 0, 0, 0.10)",
        shadowLg: "0 10px 15px -3px rgba(0, 0, 0, 0.10)",
        shadowXl: "0 20px 25px -5px rgba(0, 0, 0, 0.10)",
      },
      heavy: {
        shadowSm: "0 1px 2px 0 rgba(0, 0, 0, 0.08)",
        shadow: "0 1px 3px 0 rgba(0, 0, 0, 0.15)",
        shadowMd: "0 4px 6px -1px rgba(0, 0, 0, 0.15)",
        shadowLg: "0 10px 15px -3px rgba(0, 0, 0, 0.15)",
        shadowXl: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
      },
    };

    this.theme.shadows = { ...this.theme.shadows, ...intensityMap[intensity] };
    return this;
  }

  /**
   * Set transition timing
   */
  setTransitions(fast?: string, base?: string, slow?: string): this {
    this.theme.transitions = this.theme.transitions || {};

    if (fast) this.theme.transitions.transitionFast = fast;
    if (base) this.theme.transitions.transition = base;
    if (slow) this.theme.transitions.transitionSlow = slow;

    return this;
  }

  /**
   * Enable dark mode colors
   */
  setDarkMode(enabled = true): this {
    if (!enabled) return this;

    this.theme.colors = this.theme.colors || {};

    // Dark mode color adjustments
    this.theme.colors.background = "14.5% 0 0"; // Dark background
    this.theme.colors.foreground = "98.5% 0 0"; // Light text
    this.theme.colors.card = "20.5% 0 0"; // Slightly lighter card
    this.theme.colors.cardForeground = "98.5% 0 0";
    this.theme.colors.border = "26.9% 0 0"; // Subtle border
    this.theme.colors.input = "26.9% 0 0";
    this.theme.colors.muted = "26.9% 0 0";
    this.theme.colors.mutedForeground = "70.8% 0 0";

    return this;
  }

  /**
   * Merge with existing theme
   */
  merge(theme: EyloTheme): this {
    this.theme = {
      colors: { ...this.theme.colors, ...theme.colors },
      typography: { ...this.theme.typography, ...theme.typography },
      spacing: { ...this.theme.spacing, ...theme.spacing },
      radius: { ...this.theme.radius, ...theme.radius },
      shadows: { ...this.theme.shadows, ...theme.shadows },
      transitions: { ...this.theme.transitions, ...theme.transitions },
      zIndex: { ...this.theme.zIndex, ...theme.zIndex },
    };
    return this;
  }

  /**
   * Build and return the theme
   */
  build(): EyloTheme {
    return { ...this.theme };
  }

  /**
   * Reset builder (start fresh)
   */
  reset(): this {
    this.theme = {};
    return this;
  }
}

/**
 * Create a new theme builder instance
 */
export function createThemeBuilder(): ThemeBuilder {
  return new ThemeBuilder();
}

/**
 * Quick theme factory - Create theme with common options
 */
export function createQuickTheme(options: {
  primaryColor?: string;
  fontFamily?: string;
  radius?: "small" | "medium" | "large";
  spacing?: "compact" | "normal" | "spacious";
  darkMode?: boolean;
}): EyloTheme {
  const builder = createThemeBuilder();

  if (options.primaryColor) {
    builder.setPrimaryColor(options.primaryColor);
  }

  if (options.fontFamily) {
    builder.setFontFamily(options.fontFamily);
  }

  if (options.radius) {
    const radiusMap = {
      small: "0.375rem",
      medium: "0.65rem",
      large: "1rem",
    };
    builder.setBaseRadius(radiusMap[options.radius]);
  }

  if (options.spacing) {
    const spacingMap = {
      compact: "0.875rem",
      normal: "1rem",
      spacious: "1.125rem",
    };
    builder.setBaseSpacing(spacingMap[options.spacing]);
  }

  if (options.darkMode) {
    builder.setDarkMode(true);
  }

  return builder.build();
}
