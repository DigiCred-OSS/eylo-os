/**
 * Eylo Widget Theme System - Preset Themes
 *
 * Pre-configured theme variations for common use cases
 */

import type { ThemeConfig } from "./types";

/**
 * Minimal theme - Small border radius, subtle shadows
 */
export const minimalTheme: ThemeConfig = {
  name: "minimal",
  description: "Clean and minimal design with subtle borders",
  theme: {
    radius: {
      radiusSm: "0.25rem", // 4px
      radius: "0.375rem", // 6px
      radiusMd: "0.5rem", // 8px
      radiusLg: "0.5rem", // 8px
      radiusXl: "0.5rem", // 8px
    },
    shadows: {
      shadowSm: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
      shadow: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
      shadowMd: "0 2px 4px 0 rgba(0, 0, 0, 0.05)",
      shadowLg: "0 4px 6px 0 rgba(0, 0, 0, 0.05)",
      shadowXl: "0 8px 10px 0 rgba(0, 0, 0, 0.05)",
    },
  },
};

/**
 * Rounded theme - Large border radius, softer appearance
 */
export const roundedTheme: ThemeConfig = {
  name: "rounded",
  description: "Soft, rounded design with generous border radius",
  theme: {
    radius: {
      radiusSm: "0.75rem", // 12px
      radius: "1rem", // 16px
      radiusMd: "1.125rem", // 18px
      radiusLg: "1.25rem", // 20px
      radiusXl: "1.5rem", // 24px
    },
  },
};

/**
 * Bold theme - Strong typography, high contrast
 */
export const boldTheme: ThemeConfig = {
  name: "bold",
  description: "Strong typography with bolder font weights",
  theme: {
    typography: {
      fontMedium: 600,
      fontSemibold: 700,
      fontBold: 800,
    },
    colors: {
      // Increase contrast
      foreground: "14.5% 0 0", // Darker text
      mutedForeground: "45% 0 0", // Less subtle muted text
    },
  },
};

/**
 * Compact theme - Reduced spacing, smaller text
 */
export const compactTheme: ThemeConfig = {
  name: "compact",
  description: "Tighter spacing for information-dense interfaces",
  theme: {
    spacing: {
      spacingXs: "0.375rem", // 6px
      spacingSm: "0.625rem", // 10px
      spacing: "0.875rem", // 14px
      spacingMd: "1.25rem", // 20px
      spacingLg: "1.75rem", // 28px
      spacingXl: "2.5rem", // 40px
    },
    typography: {
      text: "0.9375rem", // 15px
      textLg: "1.0625rem", // 17px
      textXl: "1.1875rem", // 19px
    },
  },
};

/**
 * Spacious theme - Generous spacing, larger text
 */
export const spaciousTheme: ThemeConfig = {
  name: "spacious",
  description: "Generous spacing for comfortable reading",
  theme: {
    spacing: {
      spacingXs: "0.625rem", // 10px
      spacingSm: "0.875rem", // 14px
      spacing: "1.125rem", // 18px
      spacingMd: "1.75rem", // 28px
      spacingLg: "2.5rem", // 40px
      spacingXl: "3.5rem", // 56px
    },
    typography: {
      text: "1.0625rem", // 17px
      textLg: "1.1875rem", // 19px
      textXl: "1.375rem", // 22px
      leading: 1.6, // Relaxed line height
      leadingRelaxed: 1.75,
    },
  },
};

/**
 * Map of all preset themes
 */
export const presetThemes: Record<string, ThemeConfig> = {
  minimal: minimalTheme,
  rounded: roundedTheme,
  bold: boldTheme,
  compact: compactTheme,
  spacious: spaciousTheme,
};

/**
 * Get a preset theme by name
 * @param name Preset theme name
 * @returns Theme configuration or undefined
 */
export function getPresetTheme(name: string): ThemeConfig | undefined {
  return presetThemes[name];
}

/**
 * List all available preset themes
 * @returns Array of theme names
 */
export function listPresetThemes(): string[] {
  return Object.keys(presetThemes);
}
