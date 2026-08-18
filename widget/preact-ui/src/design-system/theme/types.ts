/**
 * Eylo Widget Theme System - Type Definitions
 *
 * Provides TypeScript types for all CSS custom properties in the design system.
 * Enables type-safe theme customization without sacrificing CSS performance.
 */

/**
 * OKLCH color space value
 * Format: "L C H" where:
 * - L (Lightness): 0-100%
 * - C (Chroma): 0-0.4 typically
 * - H (Hue): 0-360 degrees
 *
 * @example "62% 0.25 264" - A medium blue
 * @example "85% 0 0" - A light gray
 */
export type OKLCHColor = string;

/**
 * CSS length value (rem, px, em, etc.)
 * @example "1rem"
 * @example "16px"
 */
export type CSSLength = string;

/**
 * CSS font family
 * @example "'Inter', sans-serif"
 */
export type FontFamily = string;

/**
 * Numeric value (for font weights, z-index, line heights)
 */
export type NumericValue = number | string;

/**
 * Color tokens - Semantic color system
 */
export interface ColorTokens {
  // Background & Foreground
  background?: OKLCHColor;
  foreground?: OKLCHColor;

  // Cards
  card?: OKLCHColor;
  cardForeground?: OKLCHColor;

  // Popovers
  popover?: OKLCHColor;
  popoverForeground?: OKLCHColor;

  // Primary (main brand color)
  primary?: OKLCHColor;
  primaryForeground?: OKLCHColor;

  // Secondary
  secondary?: OKLCHColor;
  secondaryForeground?: OKLCHColor;

  // Muted (subtle backgrounds)
  muted?: OKLCHColor;
  mutedForeground?: OKLCHColor;

  // Accent (highlights)
  accent?: OKLCHColor;
  accentForeground?: OKLCHColor;

  // Destructive (errors, dangerous actions)
  destructive?: OKLCHColor;
  destructiveForeground?: OKLCHColor;

  // Success
  success?: OKLCHColor;
  successForeground?: OKLCHColor;

  // Warning
  warning?: OKLCHColor;
  warningForeground?: OKLCHColor;

  // Structural borders & interactive controls
  border?: OKLCHColor;
  controlBorder?: OKLCHColor;
  input?: OKLCHColor;
  ring?: OKLCHColor;

  // Messages
  messageUser?: OKLCHColor;
  messageUserForeground?: OKLCHColor;
  messageBot?: OKLCHColor;
  messageBotForeground?: OKLCHColor;
}

/**
 * Typography tokens - Semantic type scale
 */
export interface TypographyTokens {
  // Font families
  fontSans?: FontFamily;
  fontMono?: FontFamily;

  // Font sizes (semantic scale)
  textXs?: CSSLength; // Extra small (12px)
  textSm?: CSSLength; // Small (14px)
  text?: CSSLength; // Base/default (16px)
  textLg?: CSSLength; // Large (18px)
  textXl?: CSSLength; // Extra large (20px)
  text2xl?: CSSLength; // 2x large (24px)
  text3xl?: CSSLength; // 3x large (30px)

  // Line heights
  leadingTight?: NumericValue; // Tight (1.25)
  leading?: NumericValue; // Normal (1.5)
  leadingRelaxed?: NumericValue; // Relaxed (1.625)

  // Font weights
  fontNormal?: NumericValue; // 400
  fontMedium?: NumericValue; // 500
  fontSemibold?: NumericValue; // 600
  fontBold?: NumericValue; // 700
}

/**
 * Spacing tokens - Semantic spacing scale
 */
export interface SpacingTokens {
  spacingXs?: CSSLength; // Extra small (0.5rem / 8px)
  spacingSm?: CSSLength; // Small (0.75rem / 12px)
  spacing?: CSSLength; // Base/default (1rem / 16px)
  spacingMd?: CSSLength; // Medium (1.5rem / 24px)
  spacingLg?: CSSLength; // Large (2rem / 32px)
  spacingXl?: CSSLength; // Extra large (3rem / 48px)
  spacing2xl?: CSSLength; // 2x large (4rem / 64px)
  spacing3xl?: CSSLength; // 3x large (6rem / 96px)
}

/**
 * Border radius tokens - Semantic scale
 */
export interface RadiusTokens {
  radiusSm?: CSSLength; // Small (0.375rem / 6px)
  radius?: CSSLength; // Base/default (0.5rem / 8px)
  radiusMd?: CSSLength; // Medium (0.65rem / 10px)
  radiusLg?: CSSLength; // Large (0.75rem / 12px)
  radiusXl?: CSSLength; // Extra large (1rem / 16px)
  radiusFull?: CSSLength; // Full (9999px)
}

/**
 * Shadow tokens - Semantic elevation scale
 */
export interface ShadowTokens {
  shadowSm?: string; // Small / subtle
  shadow?: string; // Base/default
  shadowMd?: string; // Medium
  shadowLg?: string; // Large
  shadowXl?: string; // Extra large
}

/**
 * Transition tokens - Semantic timing scale
 */
export interface TransitionTokens {
  transitionFast?: string; // Fast (150ms)
  transition?: string; // Base/default (200ms)
  transitionSlow?: string; // Slow (300ms)
}

/**
 * Z-index tokens
 */
export interface ZIndexTokens {
  zBase?: NumericValue;
  zDropdown?: NumericValue;
  zSticky?: NumericValue;
  zFixed?: NumericValue;
  zModalBackdrop?: NumericValue;
  zModal?: NumericValue;
  zPopover?: NumericValue;
  zTooltip?: NumericValue;
}

/**
 * Floating button preset positions
 */
export type FloatingButtonPosition = "bottom-right" | "bottom-left" | "top-right" | "top-left";

/**
 * Custom floating button positioning
 * Allows fine-grained control over button placement
 */
export interface FloatingButtonCustomPosition {
  /** Distance from top (e.g., '2rem', '20px') */
  top?: CSSLength;
  /** Distance from bottom (e.g., '1rem', '16px') */
  bottom?: CSSLength;
  /** Distance from left (e.g., '2rem', '20px') */
  left?: CSSLength;
  /** Distance from right (e.g., '1rem', '16px') */
  right?: CSSLength;
}

/**
 * Chat container alignment relative to floating button
 * Auto-calculated based on button position
 */
export type ChatContainerAlignment =
  | "auto" // Smart: bottom->up, top->down, left->right, right->left
  | "above" // Always open above button
  | "below" // Always open below button
  | "left-aligned" // Align left edge with button
  | "right-aligned"; // Align right edge with button

/**
 * Floating button icon configuration
 */
export interface FloatingButtonIcon {
  /** Custom icon component or SVG string */
  icon?: string;
  /** Icon when widget is open (defaults to close/down arrow) */
  iconOpen?: string;
  /** Icon when widget is closed (defaults to brand icon) */
  iconClosed?: string;
  /** Icon size (e.g., '2rem', '32px') */
  iconSize?: CSSLength;
}

/**
 * Floating button configuration
 */
export interface FloatingButtonConfig {
  /** Preset position (easy setup) */
  position?: FloatingButtonPosition;
  /** Custom position (overrides preset) */
  customPosition?: FloatingButtonCustomPosition;
  /** Button size (e.g., '3.5rem', '56px') */
  size?: CSSLength;
  /** Button shape - border radius (e.g., '50%' for circle, '0.5rem' for rounded square) */
  borderRadius?: CSSLength;
  /** Button background color (OKLCH) */
  backgroundColor?: OKLCHColor;
  /** Button icon color (OKLCH) */
  iconColor?: OKLCHColor;
  /** Custom icon/logo */
  icon?: FloatingButtonIcon;
  /** Z-index for button (default: 50) */
  zIndex?: NumericValue;
  /** Gap between button and chat container in pixels (e.g., '24px', '32px'). Default: '24px' */
  containerGap?: string;
  /** Chat container alignment relative to button */
  containerAlignment?: ChatContainerAlignment;
  /** Hide button on mobile (default: false) */
  hideOnMobile?: boolean;
}

/**
 * Complete theme configuration
 * All properties are optional - only override what you need
 */
export interface EyloTheme {
  /** Base preset to start from ('minimal' | 'rounded' | 'bold' | 'compact' | 'spacious') */
  preset?: PresetThemeName;
  colors?: ColorTokens;
  typography?: TypographyTokens;
  spacing?: SpacingTokens;
  radius?: RadiusTokens;
  shadows?: ShadowTokens;
  transitions?: TransitionTokens;
  zIndex?: ZIndexTokens;
  floatingButton?: FloatingButtonConfig;
}

/**
 * Preset theme names
 */
export type PresetThemeName = "minimal" | "rounded" | "bold" | "compact" | "spacious";

/**
 * Theme configuration with metadata
 */
export interface ThemeConfig {
  name: string;
  description?: string;
  theme: EyloTheme;
}
