/**
 * # Brand Override Helpers
 *
 * Simple utilities for developers to inject their brand identity while maintaining
 * the minimalist design system principles.
 *
 * ## Quick Start
 *
 * ```typescript
 * import { applyBrandColor } from '@eylo/widget/design-system';
 *
 * // Pass your brand color in OKLCH format
 * applyBrandColor('oklch(62% 0.25 264)'); // Blue
 * ```
 *
 * **Note**: Colors must be in OKLCH format (Lightness Chroma Hue).
 * Future versions may add RGB/hex support via color scheme option.
 */

import { applyTheme } from "./apply";
import type { EyloTheme } from "./types";

/**
 * ## Apply Brand Color
 *
 * The simplest way to customize the widget with your brand identity.
 * Applies your color to all primary actions (buttons, links, focus states)
 * while maintaining the grayscale foundation.
 *
 * ### Example
 *
 * ```typescript
 * applyBrandColor('oklch(62% 0.25 264)'); // Corporate blue
 * applyBrandColor('oklch(70% 0.19 25)');  // Startup orange
 * applyBrandColor('oklch(65% 0.15 160)'); // Tech green
 * ```
 *
 * ### OKLCH Format
 * `oklch(L% C H)` where:
 * - L = Lightness (0-100%)
 * - C = Chroma (0-0.4, saturation)
 * - H = Hue (0-360°)
 *
 * ### What Changes?
 * - Primary buttons/links use your color
 * - Focus rings use your color
 * - Foreground color auto-generated for contrast
 * - Everything else stays grayscale
 */
export function applyBrandColor(oklchColor: string, element?: HTMLElement): void {
  const target = element || document.documentElement;
  applyTheme(target, {
    colors: {
      primary: oklchColor,
    },
  });
}

/**
 * ## Apply Brand Colors (Extended)
 *
 * Customize multiple semantic colors at once while maintaining the system.
 * Useful when your brand has specific colors for success/error states.
 *
 * ### Example
 *
 * ```typescript
 * applyBrandColors({
 *   primary: 'oklch(62% 0.25 264)',     // Brand blue
 *   success: 'oklch(65% 0.15 145)',     // Brand green
 *   destructive: 'oklch(58% 0.22 25)',  // Brand red
 *   warning: 'oklch(75% 0.15 85)',      // Brand yellow
 * });
 * ```
 *
 * @param colors Object with OKLCH semantic color mappings (all optional)
 */
export function applyBrandColors(
  colors: {
    primary?: string;
    secondary?: string;
    success?: string;
    destructive?: string;
    warning?: string;
  },
  element?: HTMLElement
): void {
  const target = element || document.documentElement;
  const theme: Partial<EyloTheme> = { colors: {} };

  if (colors.primary) {
    theme.colors!.primary = colors.primary;
  }
  if (colors.secondary) {
    theme.colors!.secondary = colors.secondary;
  }
  if (colors.success) {
    theme.colors!.success = colors.success;
  }
  if (colors.destructive) {
    theme.colors!.destructive = colors.destructive;
  }
  if (colors.warning) {
    theme.colors!.warning = colors.warning;
  }

  applyTheme(target, theme as EyloTheme);
}

/**
 * ## Apply Brand Typography
 *
 * Match your brand's font family and scale.
 *
 * ### Example
 *
 * ```typescript
 * applyBrandTypography({
 *   fontFamily: 'Inter, system-ui, sans-serif',
 *   baseFontSize: '16px',
 * });
 * ```
 */
export function applyBrandTypography(
  typography: {
    fontFamily?: string;
    baseFontSize?: string;
  },
  element?: HTMLElement
): void {
  const target = element || document.documentElement;
  applyTheme(target, { typography } as EyloTheme);
}

/**
 * ## Apply Complete Brand Theme
 *
 * Full brand customization in one call. Useful when you have comprehensive
 * brand guidelines that specify colors, typography, spacing, etc.
 *
 * ### Example
 *
 * ```typescript
 * applyCompleteBrandTheme({
 *   colors: {
 *     primary: 'oklch(62% 0.25 264)',
 *     secondary: 'oklch(96% 0.01 264)',
 *     success: 'oklch(65% 0.15 145)',
 *     destructive: 'oklch(58% 0.22 25)',
 *   },
 *   typography: {
 *     fontFamily: 'Inter, system-ui',
 *     baseFontSize: '16px',
 *   },
 *   spacing: {
 *     default: '1rem',
 *     large: '2rem',
 *   },
 *   radius: {
 *     default: '12px', // More rounded
 *   },
 * });
 * ```
 */
export function applyCompleteBrandTheme(
  config: {
    colors?: {
      primary?: string;
      secondary?: string;
      success?: string;
      destructive?: string;
      warning?: string;
      background?: string;
      foreground?: string;
    };
    typography?: {
      fontFamily?: string;
      baseFontSize?: string;
    };
    spacing?: {
      default?: string;
      small?: string;
      large?: string;
    };
    radius?: {
      default?: string;
      small?: string;
      large?: string;
    };
  },
  element?: HTMLElement
): void {
  const target = element || document.documentElement;
  const theme: Partial<EyloTheme> = {};

  // Pass through OKLCH colors directly
  if (config.colors) {
    theme.colors = {} as any;
    for (const [key, value] of Object.entries(config.colors)) {
      if (value) {
        (theme.colors as any)[key] = value;
      }
    }
  }

  // Pass through other configs directly
  if (config.typography) {
    theme.typography = config.typography as any;
  }
  if (config.spacing) {
    theme.spacing = config.spacing as any;
  }
  if (config.radius) {
    theme.radius = config.radius as any;
  }

  applyTheme(target, theme as EyloTheme);
}

/**
 * ## Dark Mode with Brand
 *
 * Apply dark mode while maintaining your brand color.
 * Automatically adjusts your brand color for visibility on dark backgrounds.
 *
 * ### Example
 *
 * ```typescript
 * applyDarkModeWithBrand('oklch(62% 0.25 264)');
 *
 * // Or with custom adjustments
 * applyDarkModeWithBrand('oklch(62% 0.25 264)', {
 *   lightenBy: 20, // Make brand color lighter by 20% for dark bg
 * });
 * ```
 */
export function applyDarkModeWithBrand(
  brandColor: string,
  options?: { lightenBy?: number; element?: HTMLElement }
): void {
  const target = options?.element || document.documentElement;

  // Parse OKLCH to adjust lightness
  const match = brandColor.match(/oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+)/);
  if (!match) {
    throw new Error("Invalid OKLCH color format");
  }

  let lightness = parseFloat(match[1]);
  const chroma = parseFloat(match[2]);
  const hue = parseFloat(match[3]);

  // Lighten brand color for dark mode visibility
  const adjustment = options?.lightenBy ?? 15;
  lightness = Math.min(100, lightness + adjustment);

  const adjustedBrand = `oklch(${lightness}% ${chroma} ${hue})`;

  applyTheme(target, {
    colors: {
      // Dark mode backgrounds
      background: "oklch(15% 0 0)", // gray-950
      foreground: "oklch(98% 0 0)", // gray-50

      card: "oklch(15% 0 0)",
      cardForeground: "oklch(98% 0 0)",

      popover: "oklch(15% 0 0)",
      popoverForeground: "oklch(98% 0 0)",

      // Brand color adjusted for dark mode
      primary: adjustedBrand,

      // Muted/secondary slightly lighter in dark mode
      secondary: "oklch(20% 0 0)", // gray-900
      secondaryForeground: "oklch(98% 0 0)",

      muted: "oklch(20% 0 0)",
      mutedForeground: "oklch(64% 0 0)", // gray-400

      accent: "oklch(20% 0 0)",
      accentForeground: "oklch(98% 0 0)",

      // Borders lighter in dark mode
      border: "oklch(32% 0 0)", // gray-800
      input: "oklch(32% 0 0)",
      ring: "oklch(46% 0 0)", // gray-600
    },
  } as EyloTheme);
}

/**
 * ## Reset to Default Theme
 *
 * Remove all customizations and revert to the default minimalist theme.
 *
 * ### Example
 *
 * ```typescript
 * import { resetToDefault } from '@eylo/widget/design-system';
 *
 * // User changed theme preference, reset
 * resetToDefault();
 * ```
 */
export function resetToDefault(): void {
  // Remove all CSS custom property overrides
  const root = document.documentElement;
  const computedStyle = getComputedStyle(root);

  // Get all custom properties starting with --ew-
  const ewProperties = Array.from(computedStyle).filter((prop) => prop.startsWith("--ew-"));

  // Remove inline style overrides (reverts to stylesheet defaults)
  ewProperties.forEach((prop) => {
    root.style.removeProperty(prop);
  });
}

/**
 * ## Example Usage Patterns
 *
 * ### Simple Brand Color
 * ```typescript
 * import { applyBrandColor } from '@eylo/widget/design-system';
 * applyBrandColor('oklch(62% 0.25 264)');
 * ```
 *
 * ### Brand + Dark Mode
 * ```typescript
 * import { applyBrandColor, applyDarkModeWithBrand } from '@eylo/widget/design-system';
 *
 * const brandColor = 'oklch(62% 0.25 264)';
 * const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
 * if (isDark) {
 *   applyDarkModeWithBrand(brandColor);
 * } else {
 *   applyBrandColor(brandColor);
 * }
 * ```
 *
 * ### Complete Brand System
 * ```typescript
 * import { applyCompleteBrandTheme } from '@eylo/widget/design-system';
 *
 * applyCompleteBrandTheme({
 *   colors: {
 *     primary: 'oklch(62% 0.25 264)',
 *     success: 'oklch(65% 0.15 145)',
 *     destructive: 'oklch(58% 0.22 25)',
 *   },
 *   typography: {
 *     fontFamily: 'Inter, system-ui',
 *   },
 * });
 * ```
 */
