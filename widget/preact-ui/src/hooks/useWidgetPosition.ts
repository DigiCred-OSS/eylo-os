// hooks/useWidgetPosition.ts
import { useEffect, useState } from "preact/hooks";
import type { TChatButtonDimensions } from "../components/ChatFloatingButton";

/**
 * Hook to manage widget positioning based on floating button
 * with smart alignment based on button location
 *
 * Note: Theme config uses rem for user-friendly configuration,
 * but dynamic runtime calculations use px for accuracy with getBoundingClientRect()
 */
export function useWidgetPosition() {
  const [floatingButtonPosition, setFloatingButtonPosition] = useState<TChatButtonDimensions>({
    x: 0,
    y: 0,
    width: 0,
    height: 0,
  });

  const [widgetStyle, setWidgetStyle] = useState<{
    bottom?: string;
    top?: string;
    right?: string;
    left?: string;
    height: string;
  }>({
    bottom: "80px",
    right: "16px",
    height: "calc(100vh - 110px)",
  });

  useEffect(() => {
    if (floatingButtonPosition.width === 0) return;

    // Get button config from CSS variables
    const widgetRoot = document.getElementById("eylo-widget");
    if (!widgetRoot) return;

    const computedStyle = getComputedStyle(widgetRoot);
    const vertical = computedStyle.getPropertyValue("--ew-container-vertical").trim();
    const horizontal = computedStyle.getPropertyValue("--ew-container-horizontal").trim();
    const gap = parseFloat(computedStyle.getPropertyValue("--ew-button-container-gap") || "8");

    // Calculate position based on alignment
    const viewport = {
      width: window.innerWidth,
      height: window.innerHeight,
    };

    const buttonRect = new DOMRect(
      floatingButtonPosition.x,
      floatingButtonPosition.y,
      floatingButtonPosition.width,
      floatingButtonPosition.height
    );

    const newStyle: typeof widgetStyle = {
      height: "calc(100vh - 110px)",
    };

    // Vertical positioning (use px for accuracy with viewport calculations)
    if (vertical === "above" || !vertical) {
      // Open above button (default behavior)
      const availableSpace = buttonRect.top - gap;
      const bottomOffset = viewport.height - buttonRect.top + gap;
      newStyle.bottom = `${bottomOffset}px`;
      newStyle.height = `min(${availableSpace}px, 90vh)`;
    } else {
      // Open below button
      const availableSpace = viewport.height - buttonRect.bottom - gap;
      const topOffset = buttonRect.bottom + gap;
      newStyle.top = `${topOffset}px`;
      newStyle.height = `min(${availableSpace}px, 90vh)`;
    }

    // Horizontal positioning (use px for accuracy with viewport calculations)
    if (horizontal === "left") {
      // Align left edge with button's left edge
      newStyle.left = `${buttonRect.left}px`;
    } else {
      // Align right edge with button's right edge (default)
      const rightOffset = viewport.width - buttonRect.right;
      newStyle.right = `${rightOffset}px`;
    }

    setWidgetStyle(newStyle);
  }, [floatingButtonPosition]);

  return {
    floatingButtonPosition,
    setFloatingButtonPosition,
    widgetStyle,
  };
}
