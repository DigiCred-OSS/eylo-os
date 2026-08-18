import { forwardRef } from "preact/compat";
import type { JSX, ComponentChildren } from "preact";
import { createContext } from "preact";
import { useContext, useState, useEffect, useRef } from "preact/hooks";
import { cm } from "../utils";
import styles from "./Popover.module.css";

// Context for Popover state
interface PopoverContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: { current: HTMLDivElement | null };
}

const PopoverContext = createContext<PopoverContextValue | null>(null);

const usePopover = () => {
  const context = useContext(PopoverContext);
  if (!context) {
    throw new Error("Popover components must be used within Popover");
  }
  return context;
};

// Popover Root Component
export interface PopoverProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  defaultOpen?: boolean;
  children: ComponentChildren;
}

export const Popover = ({
  open: controlledOpen,
  onOpenChange,
  defaultOpen = false,
  children,
}: PopoverProps) => {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const triggerRef = useRef<HTMLDivElement | null>(null);

  const open = controlledOpen !== undefined ? controlledOpen : uncontrolledOpen;
  const setOpen = (newOpen: boolean) => {
    if (controlledOpen === undefined) {
      setUncontrolledOpen(newOpen);
    }
    onOpenChange?.(newOpen);
  };

  return (
    <PopoverContext.Provider value={{ open, setOpen, triggerRef }}>
      {children}
    </PopoverContext.Provider>
  );
};

// PopoverTrigger Component
export interface PopoverTriggerProps extends JSX.HTMLAttributes<HTMLElement> {
  asChild?: boolean;
}

export const PopoverTrigger = ({ className, children, ...props }: PopoverTriggerProps) => {
  const { setOpen, triggerRef } = usePopover();

  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
    setOpen(true);
  };

  const handleRef = (el: HTMLDivElement | null) => {
    (triggerRef as any).current = el;
  };

  return (
    <div
      ref={handleRef as any}
      className={cm(styles.popoverTrigger, className)}
      onClick={handleClick}
      {...props}
    >
      {children}
    </div>
  );
};

// PopoverContent Component
export interface PopoverContentProps extends JSX.HTMLAttributes<HTMLDivElement> {
  side?: "top" | "bottom" | "left" | "right";
  align?: "start" | "center" | "end";
  sideOffset?: number;
  alignOffset?: number;
  showArrow?: boolean;
  showClose?: boolean;
}

export const PopoverContent = forwardRef<HTMLDivElement, PopoverContentProps>(
  (
    {
      className,
      side = "bottom",
      align = "center",
      sideOffset = 8,
      alignOffset = 0,
      showArrow = false,
      showClose = false,
      children,
      ...props
    },
    ref
  ) => {
    const { open, setOpen, triggerRef } = usePopover();
    const contentRef = useRef<HTMLDivElement>(null);
    const [position, setPosition] = useState({ top: 0, left: 0 });

    // Combine refs
    const setRefs = (el: HTMLDivElement | null) => {
      contentRef.current = el;
      if (typeof ref === "function") ref(el);
      else if (ref) (ref as any).current = el;
    };

    // Calculate position based on trigger
    useEffect(() => {
      if (open && triggerRef.current && contentRef.current) {
        const triggerRect = triggerRef.current.getBoundingClientRect();
        const contentRect = contentRef.current.getBoundingClientRect();

        let top = 0;
        let left = 0;

        // Calculate position based on side
        switch (side) {
          case "top":
            top = triggerRect.top - contentRect.height - sideOffset;
            break;
          case "bottom":
            top = triggerRect.bottom + sideOffset;
            break;
          case "left":
            left = triggerRect.left - contentRect.width - sideOffset;
            break;
          case "right":
            left = triggerRect.right + sideOffset;
            break;
        }

        // Calculate align offset
        if (side === "top" || side === "bottom") {
          switch (align) {
            case "start":
              left = triggerRect.left + alignOffset;
              break;
            case "center":
              left = triggerRect.left + triggerRect.width / 2 - contentRect.width / 2 + alignOffset;
              break;
            case "end":
              left = triggerRect.right - contentRect.width + alignOffset;
              break;
          }
        } else {
          switch (align) {
            case "start":
              top = triggerRect.top + alignOffset;
              break;
            case "center":
              top = triggerRect.top + triggerRect.height / 2 - contentRect.height / 2 + alignOffset;
              break;
            case "end":
              top = triggerRect.bottom - contentRect.height + alignOffset;
              break;
          }
        }

        setPosition({ top, left });
      }
    }, [open, side, align, sideOffset, alignOffset]);

    // Close on click outside
    useEffect(() => {
      if (!open) return;

      const handleClickOutside = (e: MouseEvent) => {
        if (
          contentRef.current &&
          !contentRef.current.contains(e.target as Node) &&
          triggerRef.current &&
          !triggerRef.current.contains(e.target as Node)
        ) {
          setOpen(false);
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [open, setOpen, triggerRef]);

    // Close on Escape
    useEffect(() => {
      if (!open) return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          setOpen(false);
        }
      };

      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }, [open, setOpen]);

    if (!open) return null;

    return (
      <div
        ref={setRefs}
        className={cm(styles.popoverContent, className)}
        data-side={side}
        style={{ position: "fixed", top: `${position.top}px`, left: `${position.left}px` }}
        role="dialog"
        aria-modal="true"
        {...props}
      >
        {showArrow && <div className={styles.popoverArrow} />}
        {children}
        {showClose && (
          <button className={styles.popoverClose} onClick={() => setOpen(false)} aria-label="Close">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        )}
      </div>
    );
  }
);

// PopoverClose Component
export interface PopoverCloseProps extends JSX.HTMLAttributes<HTMLButtonElement> {}

export const PopoverClose = forwardRef<HTMLButtonElement, PopoverCloseProps>(
  ({ className, children, ...props }, ref) => {
    const { setOpen } = usePopover();

    return (
      <button
        ref={ref}
        type="button"
        className={className}
        onClick={() => setOpen(false)}
        {...props}
      >
        {children}
      </button>
    );
  }
);
