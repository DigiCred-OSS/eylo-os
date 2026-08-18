/**
 * Eylo Widget Theme System - Floating Button Configuration
 *
 * Utilities for configuring and positioning the floating button
 * with smart chat container alignment
 */

import type {
  ChatContainerAlignment,
  CSSLength,
  FloatingButtonConfig,
  FloatingButtonCustomPosition,
  FloatingButtonPosition,
} from "./types";

/**
 * Preset position configurations
 */
const PRESET_POSITIONS: Record<FloatingButtonPosition, FloatingButtonCustomPosition> = {
  "bottom-right": {
    bottom: "1rem",
    right: "1rem",
  },
  "bottom-left": {
    bottom: "1rem",
    left: "1rem",
  },
  "top-right": {
    top: "1rem",
    right: "1rem",
  },
  "top-left": {
    top: "1rem",
    left: "1rem",
  },
};

/**
 * Calculate chat container alignment based on button position
 *
 * @param buttonPosition Button position (preset or custom)
 * @param alignment Desired alignment (defaults to 'auto')
 * @returns Calculated alignment strategy
 */
export function calculateContainerAlignment(
  buttonPosition: FloatingButtonCustomPosition,
  alignment: ChatContainerAlignment = "auto"
): {
  vertical: "above" | "below";
  horizontal: "left" | "right";
} {
  if (alignment === "above") {
    return { vertical: "above", horizontal: buttonPosition.right ? "right" : "left" };
  }
  if (alignment === "below") {
    return { vertical: "below", horizontal: buttonPosition.right ? "right" : "left" };
  }
  if (alignment === "left-aligned") {
    return { vertical: buttonPosition.bottom ? "above" : "below", horizontal: "left" };
  }
  if (alignment === "right-aligned") {
    return { vertical: buttonPosition.bottom ? "above" : "below", horizontal: "right" };
  }

  // Auto mode: Smart positioning based on button location
  const vertical = buttonPosition.bottom ? "above" : "below";
  const horizontal = buttonPosition.right ? "right" : "left";

  return { vertical, horizontal };
}

/**
 * Resolve floating button position
 * Custom position takes precedence over preset
 *
 * @param config Floating button configuration
 * @returns Resolved position values
 */
export function resolveButtonPosition(config: FloatingButtonConfig): FloatingButtonCustomPosition {
  // Custom position overrides preset
  if (config.customPosition) {
    return config.customPosition;
  }

  // Use preset if specified
  if (config.position) {
    return PRESET_POSITIONS[config.position];
  }

  // Default to bottom-right
  return PRESET_POSITIONS["bottom-right"];
}

/**
 * Apply floating button configuration to element
 * Sets CSS custom properties for button positioning and styling
 *
 * @param element Target element (widget root)
 * @param config Floating button configuration
 */
export function applyFloatingButtonConfig(
  element: HTMLElement,
  config: FloatingButtonConfig
): void {
  const position = resolveButtonPosition(config);

  // Apply position
  if (position.top !== undefined) {
    element.style.setProperty("--ew-button-top", position.top);
    element.style.setProperty("--ew-button-bottom", "auto");
  } else if (position.bottom !== undefined) {
    element.style.setProperty("--ew-button-bottom", position.bottom);
    element.style.setProperty("--ew-button-top", "auto");
  }

  if (position.left !== undefined) {
    element.style.setProperty("--ew-button-left", position.left);
    element.style.setProperty("--ew-button-right", "auto");
  } else if (position.right !== undefined) {
    element.style.setProperty("--ew-button-right", position.right);
    element.style.setProperty("--ew-button-left", "auto");
  }

  // Apply size
  if (config.size) {
    element.style.setProperty("--ew-button-size", config.size);
  }

  // Apply border radius
  if (config.borderRadius) {
    element.style.setProperty("--ew-button-radius", config.borderRadius);
  }

  // Apply colors
  if (config.backgroundColor) {
    element.style.setProperty("--ew-button-bg", config.backgroundColor);
  }
  if (config.iconColor) {
    element.style.setProperty("--ew-button-icon-color", config.iconColor);
  }

  // Apply z-index
  if (config.zIndex !== undefined) {
    element.style.setProperty("--ew-button-z-index", String(config.zIndex));
  }

  // Apply container gap (expects px value, e.g., '24px')
  if (config.containerGap) {
    element.style.setProperty("--ew-button-container-gap", config.containerGap);
  }

  // Calculate and apply container alignment
  const alignment = calculateContainerAlignment(position, config.containerAlignment);
  element.style.setProperty("--ew-container-vertical", alignment.vertical);
  element.style.setProperty("--ew-container-horizontal", alignment.horizontal);

  // Apply mobile visibility
  if (config.hideOnMobile) {
    element.style.setProperty("--ew-button-mobile-display", "none");
  }
}

/**
 * Parse CSS length to pixels for calculations
 * Supports rem, px, em (approximations)
 *
 * @param length CSS length value
 * @param baseFontSize Base font size in pixels (default: 16)
 * @returns Pixel value
 */
export function parseCSSLength(length: CSSLength, baseFontSize = 16): number {
  if (length.endsWith("px")) {
    return parseFloat(length);
  }
  if (length.endsWith("rem")) {
    return parseFloat(length) * baseFontSize;
  }
  if (length.endsWith("em")) {
    return parseFloat(length) * baseFontSize;
  }
  return parseFloat(length) || 0;
}

/**
 * Calculate chat container position based on button dimensions
 *
 * @param buttonRect Button bounding client rect
 * @param buttonConfig Button configuration
 * @param viewportWidth Viewport width
 * @param viewportHeight Viewport height
 * @returns Container position style
 */
export function calculateContainerPosition(
  buttonRect: DOMRect,
  buttonConfig: FloatingButtonConfig,
  viewportWidth: number,
  viewportHeight: number
): {
  top?: string;
  bottom?: string;
  left?: string;
  right?: string;
  height: string;
  maxWidth: string;
} {
  const position = resolveButtonPosition(buttonConfig);
  const alignment = calculateContainerAlignment(position, buttonConfig.containerAlignment);
  const gap = parseCSSLength(buttonConfig.containerGap || "24px");

  const result: ReturnType<typeof calculateContainerPosition> = {
    maxWidth: "min(32rem, 90vw)",
    height: "90vh",
  };

  // Vertical positioning
  if (alignment.vertical === "above") {
    // Open above button
    const availableSpace = buttonRect.top - gap;
    result.bottom = `${viewportHeight - buttonRect.top + gap}px`;
    result.height = `min(${availableSpace}px, 90vh)`;
  } else {
    // Open below button
    const availableSpace = viewportHeight - buttonRect.bottom - gap;
    result.top = `${buttonRect.bottom + gap}px`;
    result.height = `min(${availableSpace}px, 90vh)`;
  }

  // Horizontal positioning
  if (alignment.horizontal === "right") {
    // Align right edge with button's right edge
    result.right = `${viewportWidth - buttonRect.right}px`;
  } else {
    // Align left edge with button's left edge
    result.left = `${buttonRect.left}px`;
  }

  return result;
}
