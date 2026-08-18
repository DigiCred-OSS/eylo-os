/**
 * Eylo Widget Theme System - Apply Functions
 *
 * Core functions to apply themes to the DOM
 */

import { applyFloatingButtonConfig } from "./floating-button";
import type {
  ColorTokens,
  EyloTheme,
  RadiusTokens,
  ShadowTokens,
  SpacingTokens,
  TransitionTokens,
  TypographyTokens,
  ZIndexTokens,
} from "./types";
import { isValidLength, isValidOKLCH, toCSSVariable } from "./utils";

/**
 * Apply theme to an element by setting CSS custom properties
 *
 * @param element Target element (typically the widget root)
 * @param theme Theme configuration
 * @param options Apply options
 */
export function applyTheme(
  element: HTMLElement,
  theme: EyloTheme,
  options: ApplyThemeOptions = {}
): void {
  const { validate = true, merge = true } = options;

  if (theme.colors) {
    applyColorTokens(element, theme.colors, { validate, merge });
  }

  if (theme.typography) {
    applyTypographyTokens(element, theme.typography, { validate, merge });
  }

  if (theme.spacing) {
    applySpacingTokens(element, theme.spacing, { validate, merge });
  }

  if (theme.radius) {
    applyRadiusTokens(element, theme.radius, { validate, merge });
  }

  if (theme.shadows) {
    applyShadowTokens(element, theme.shadows, { validate, merge });
  }

  if (theme.transitions) {
    applyTransitionTokens(element, theme.transitions, { validate, merge });
  }

  if (theme.zIndex) {
    applyZIndexTokens(element, theme.zIndex, { validate, merge });
  }

  if (theme.floatingButton) {
    applyFloatingButtonConfig(element, theme.floatingButton);
  }
}

/**
 * Apply color tokens
 */
function applyColorTokens(
  element: HTMLElement,
  colors: ColorTokens,
  options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(colors)) {
    if (value === undefined) continue;

    if (options.validate && !isValidOKLCH(value)) {
      console.warn(`[Eylo Theme] Invalid OKLCH color for ${key}: ${value}`);
      continue;
    }

    element.style.setProperty(toCSSVariable(key), value);
  }
}

/**
 * Apply typography tokens
 */
function applyTypographyTokens(
  element: HTMLElement,
  typography: TypographyTokens,
  options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(typography)) {
    if (value === undefined) continue;

    // Font families don't need validation
    if (key.startsWith("font") && (key.endsWith("Sans") || key.endsWith("Mono"))) {
      element.style.setProperty(toCSSVariable(key), value.toString());
      continue;
    }

    // Validate lengths for font sizes
    if (
      key.startsWith("text") &&
      options.validate &&
      typeof value === "string" &&
      !isValidLength(value)
    ) {
      console.warn(`[Eylo Theme] Invalid length for ${key}: ${value}`);
      continue;
    }

    element.style.setProperty(toCSSVariable(key), value.toString());
  }
}

/**
 * Apply spacing tokens
 */
function applySpacingTokens(
  element: HTMLElement,
  spacing: SpacingTokens,
  options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(spacing)) {
    if (value === undefined) continue;

    if (options.validate && !isValidLength(value)) {
      console.warn(`[Eylo Theme] Invalid spacing value for ${key}: ${value}`);
      continue;
    }

    element.style.setProperty(toCSSVariable(key), value);
  }
}

/**
 * Apply radius tokens
 */
function applyRadiusTokens(
  element: HTMLElement,
  radius: RadiusTokens,
  options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(radius)) {
    if (value === undefined) continue;

    if (options.validate && value !== "9999px" && !isValidLength(value)) {
      console.warn(`[Eylo Theme] Invalid radius value for ${key}: ${value}`);
      continue;
    }

    element.style.setProperty(toCSSVariable(key), value);
  }
}

/**
 * Apply shadow tokens
 */
function applyShadowTokens(
  element: HTMLElement,
  shadows: ShadowTokens,
  _options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(shadows)) {
    if (value === undefined) continue;
    element.style.setProperty(toCSSVariable(key), value);
  }
}

/**
 * Apply transition tokens
 */
function applyTransitionTokens(
  element: HTMLElement,
  transitions: TransitionTokens,
  _options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(transitions)) {
    if (value === undefined) continue;
    element.style.setProperty(toCSSVariable(key), value);
  }
}

/**
 * Apply z-index tokens
 */
function applyZIndexTokens(
  element: HTMLElement,
  zIndex: ZIndexTokens,
  _options: { validate: boolean; merge: boolean }
): void {
  for (const [key, value] of Object.entries(zIndex)) {
    if (value === undefined) continue;
    element.style.setProperty(toCSSVariable(key), value.toString());
  }
}

/**
 * Remove theme from element (reset to defaults)
 *
 * @param element Target element
 * @param tokens Optional array of specific tokens to remove
 */
export function removeTheme(element: HTMLElement, tokens?: string[]): void {
  if (tokens) {
    // Remove specific tokens
    tokens.forEach((token) => {
      element.style.removeProperty(toCSSVariable(token));
    });
  } else {
    // Remove all --ew-* custom properties
    Array.from(element.style).forEach((property) => {
      if (property.startsWith("--ew-")) {
        element.style.removeProperty(property);
      }
    });
  }
}

/**
 * Get current theme values from element
 *
 * @param element Target element
 * @returns Object with all CSS custom property values
 */
export function getTheme(element: HTMLElement): Record<string, string> {
  const computedStyle = getComputedStyle(element);
  const theme: Record<string, string> = {};

  Array.from(element.style).forEach((property) => {
    if (property.startsWith("--ew-")) {
      theme[property] = computedStyle.getPropertyValue(property).trim();
    }
  });

  return theme;
}

/**
 * Apply theme options
 */
export interface ApplyThemeOptions {
  /**
   * Validate values before applying (default: true)
   */
  validate?: boolean;

  /**
   * Merge with existing theme or replace (default: true)
   */
  merge?: boolean;
}

/**
 * Create a scoped theme applier for a specific element
 *
 * @param element Target element
 * @returns Object with theme methods
 */
export function createThemeManager(element: HTMLElement) {
  return {
    /**
     * Apply a theme
     */
    apply: (theme: EyloTheme, options?: ApplyThemeOptions) => {
      applyTheme(element, theme, options);
    },

    /**
     * Remove theme (reset to defaults)
     */
    reset: (tokens?: string[]) => {
      removeTheme(element, tokens);
    },

    /**
     * Get current theme values
     */
    get: () => {
      return getTheme(element);
    },

    /**
     * Get a specific token value
     */
    getToken: (token: string): string | null => {
      const computedStyle = getComputedStyle(element);
      return computedStyle.getPropertyValue(toCSSVariable(token)).trim() || null;
    },

    /**
     * Set a specific token value
     */
    setToken: (token: string, value: string) => {
      element.style.setProperty(toCSSVariable(token), value);
    },
  };
}
