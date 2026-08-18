import { forwardRef } from "preact/compat";
import type { JSX, ComponentChildren } from "preact";
import { createContext } from "preact";
import { useContext, useState, useEffect, useRef } from "preact/hooks";
import { cm } from "../utils";
import styles from "./DropdownMenu.module.css";

// Context for Dropdown Menu state
interface DropdownMenuContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  triggerRef: { current: HTMLDivElement | null };
}

const DropdownMenuContext = createContext<DropdownMenuContextValue | null>(null);

const useDropdownMenu = () => {
  const context = useContext(DropdownMenuContext);
  if (!context) {
    throw new Error("DropdownMenu components must be used within DropdownMenu");
  }
  return context;
};

// DropdownMenu Root Component
export interface DropdownMenuProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  defaultOpen?: boolean;
  children: ComponentChildren;
}

export const DropdownMenu = ({
  open: controlledOpen,
  onOpenChange,
  defaultOpen = false,
  children,
}: DropdownMenuProps) => {
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
    <DropdownMenuContext.Provider value={{ open, setOpen, triggerRef }}>
      {children}
    </DropdownMenuContext.Provider>
  );
};

// DropdownMenuTrigger Component
export interface DropdownMenuTriggerProps extends JSX.HTMLAttributes<HTMLElement> {
  asChild?: boolean;
}

export const DropdownMenuTrigger = ({
  className,
  children,
  ...props
}: DropdownMenuTriggerProps) => {
  const { open, setOpen, triggerRef } = useDropdownMenu();

  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
    setOpen(!open);
  };

  const handleRef = (el: HTMLDivElement | null) => {
    (triggerRef as any).current = el;
  };

  return (
    <div
      ref={handleRef as any}
      className={cm(styles.dropdownMenuTrigger, className)}
      onClick={handleClick}
      aria-haspopup="true"
      aria-expanded={open}
      {...props}
    >
      {children}
    </div>
  );
};

// DropdownMenuContent Component
export interface DropdownMenuContentProps extends JSX.HTMLAttributes<HTMLDivElement> {
  align?: "start" | "center" | "end";
  sideOffset?: number;
  alignOffset?: number;
}

export const DropdownMenuContent = forwardRef<HTMLDivElement, DropdownMenuContentProps>(
  ({ className, align = "start", sideOffset = 8, alignOffset = 0, children, ...props }, ref) => {
    const { open, setOpen, triggerRef } = useDropdownMenu();
    const contentRef = useRef<HTMLDivElement>(null);
    const [position, setPosition] = useState({ top: 0, left: 0 });

    // Combine refs
    const setRefs = (el: HTMLDivElement | null) => {
      contentRef.current = el;
      if (typeof ref === "function") ref(el);
      else if (ref) (ref as any).current = el;
    };

    // Calculate position
    useEffect(() => {
      if (open && triggerRef.current && contentRef.current) {
        const triggerRect = triggerRef.current.getBoundingClientRect();
        const contentRect = contentRef.current.getBoundingClientRect();

        let top = triggerRect.bottom + sideOffset;
        let left = 0;

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

        // Keep within viewport
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (left + contentRect.width > viewportWidth) {
          left = viewportWidth - contentRect.width - 8;
        }
        if (left < 8) {
          left = 8;
        }
        if (top + contentRect.height > viewportHeight) {
          top = triggerRect.top - contentRect.height - sideOffset;
        }

        setPosition({ top, left });
      }
    }, [open, align, sideOffset, alignOffset]);

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

    // Keyboard navigation
    useEffect(() => {
      if (!open || !contentRef.current) return;

      const items = contentRef.current.querySelectorAll(
        '[role="menuitem"]:not([data-disabled="true"])'
      );
      let currentIndex = -1;

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          currentIndex = (currentIndex + 1) % items.length;
          (items[currentIndex] as HTMLElement).focus();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          currentIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
          (items[currentIndex] as HTMLElement).focus();
        }
      };

      contentRef.current.addEventListener("keydown", handleKeyDown);
      return () => contentRef.current?.removeEventListener("keydown", handleKeyDown);
    }, [open]);

    if (!open) return null;

    return (
      <div
        ref={setRefs}
        className={cm(styles.dropdownMenuContent, className)}
        style={{ position: "fixed", top: `${position.top}px`, left: `${position.left}px` }}
        role="menu"
        {...props}
      >
        {children}
      </div>
    );
  }
);

// DropdownMenuItem Component
export interface DropdownMenuItemProps extends JSX.HTMLAttributes<HTMLDivElement> {
  disabled?: boolean;
  destructive?: boolean;
  icon?: ComponentChildren;
  shortcut?: string;
  onSelect?: () => void;
}

export const DropdownMenuItem = forwardRef<HTMLDivElement, DropdownMenuItemProps>(
  (
    {
      className,
      disabled = false,
      destructive = false,
      icon,
      shortcut,
      onSelect,
      children,
      ...props
    },
    ref
  ) => {
    const { setOpen } = useDropdownMenu();

    const handleClick = () => {
      if (!disabled) {
        onSelect?.();
        setOpen(false);
      }
    };

    return (
      <div
        ref={ref}
        role="menuitem"
        tabIndex={disabled ? -1 : 0}
        className={cm(styles.dropdownMenuItem, className)}
        data-disabled={disabled}
        data-destructive={destructive}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleClick();
          }
        }}
        {...props}
      >
        {icon && <span className={styles.dropdownMenuItemIcon}>{icon}</span>}
        {children}
        {shortcut && <span className={styles.dropdownMenuItemShortcut}>{shortcut}</span>}
      </div>
    );
  }
);

// DropdownMenuCheckboxItem Component
export interface DropdownMenuCheckboxItemProps extends JSX.HTMLAttributes<HTMLDivElement> {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
}

export const DropdownMenuCheckboxItem = forwardRef<HTMLDivElement, DropdownMenuCheckboxItemProps>(
  ({ className, checked = false, onCheckedChange, disabled = false, children, ...props }, ref) => {
    const handleClick = () => {
      if (!disabled) {
        onCheckedChange?.(!checked);
      }
    };

    return (
      <div
        ref={ref}
        role="menuitemcheckbox"
        aria-checked={checked}
        tabIndex={disabled ? -1 : 0}
        className={cm(styles.dropdownMenuItem, styles.dropdownMenuCheckboxItem, className)}
        data-disabled={disabled}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleClick();
          }
        }}
        {...props}
      >
        <span className={styles.dropdownMenuItemIndicator}>
          {checked && (
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
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          )}
        </span>
        {children}
      </div>
    );
  }
);

// DropdownMenuLabel Component
export interface DropdownMenuLabelProps extends JSX.HTMLAttributes<HTMLDivElement> {}

export const DropdownMenuLabel = forwardRef<HTMLDivElement, DropdownMenuLabelProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.dropdownMenuLabel, className)} {...props}>
        {children}
      </div>
    );
  }
);

// DropdownMenuSeparator Component
export interface DropdownMenuSeparatorProps extends JSX.HTMLAttributes<HTMLDivElement> {}

export const DropdownMenuSeparator = forwardRef<HTMLDivElement, DropdownMenuSeparatorProps>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="separator"
        className={cm(styles.dropdownMenuSeparator, className)}
        {...props}
      />
    );
  }
);
