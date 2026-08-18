/**
 * Eylo Widget Theme System
 *
 * Type-safe theme customization for the Eylo Widget design system.
 * Provides TypeScript helpers while maintaining zero-runtime CSS performance.
 *
 * @example Basic usage
 * ```ts
 * import { applyTheme } from '@eylo/widget/theme';
 *
 * const element = document.getElementById('eylo-widget');
 * applyTheme(element, {
 *   colors: {
 *     primary: '62% 0.25 264', // Blue in OKLCH
 *   }
 * });
 * ```
 *
 * @example Using theme builder
 * ```ts
 * import { createThemeBuilder } from '@eylo/widget/theme';
 *
 * const theme = createThemeBuilder()
 *   .setPrimaryColor('62% 0.25 264')
 *   .setFontFamily('Inter, sans-serif')
 *   .setBaseRadius('0.75rem')
 *   .build();
 *
 * applyTheme(element, theme);
 * ```
 *
 * @example Using presets
 * ```ts
 * import { getPresetTheme, applyTheme } from '@eylo/widget/theme';
 *
 * const rounded = getPresetTheme('rounded');
 * if (rounded) {
 *   applyTheme(element, rounded.theme);
 * }
 * ```
 */

// Types
export type {
  ChatContainerAlignment,
  ColorTokens,
  CSSLength,
  EyloTheme,
  FloatingButtonConfig,
  FloatingButtonCustomPosition,
  FloatingButtonIcon,
  FloatingButtonPosition,
  FontFamily,
  NumericValue,
  OKLCHColor,
  PresetThemeName,
  RadiusTokens,
  ShadowTokens,
  SpacingTokens,
  ThemeConfig,
  TransitionTokens,
  TypographyTokens,
  ZIndexTokens,
} from "./types";

// Apply functions
export { applyTheme, createThemeManager, getTheme, removeTheme } from "./apply";
export type { ApplyThemeOptions } from "./apply";

// Theme builder
export { createQuickTheme, createThemeBuilder, ThemeBuilder } from "./builder";

// Presets
export {
  boldTheme,
  compactTheme,
  getPresetTheme,
  listPresetThemes,
  minimalTheme,
  presetThemes,
  roundedTheme,
  spaciousTheme,
} from "./presets";

// Utilities
export {
  adjustLightness,
  camelToKebab,
  createColorScale,
  generateForeground,
  hexToOKLCH,
  isValidLength,
  isValidOKLCH,
  mergeThemes,
  parseLength,
  toCSSVariable,
} from "./utils";

// Brand Override Helpers
export {
  applyBrandColor,
  applyBrandColors,
  applyBrandTypography,
  applyCompleteBrandTheme,
  applyDarkModeWithBrand,
  resetToDefault,
} from "./brand-override";

// Floating Button Configuration
export {
  applyFloatingButtonConfig,
  calculateContainerAlignment,
  calculateContainerPosition,
  resolveButtonPosition,
} from "./floating-button";
