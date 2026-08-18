import { type ComponentChildren } from "preact";
import { useState } from "preact/hooks";
import { cm } from "../utils";
import styles from "./Tooltip.module.css";

export interface TooltipProps {
  content: ComponentChildren;
  side?: "top" | "bottom" | "left" | "right";
  children: ComponentChildren;
  className?: string;
}

export const Tooltip = ({ content, side = "top", children, className }: TooltipProps) => {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div
      className={cm(styles.tooltip, className)}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      <div className={styles.trigger}>{children}</div>
      {isVisible && (
        <div className={styles.content} data-side={side}>
          {content}
        </div>
      )}
    </div>
  );
};

Tooltip.displayName = "Tooltip";
