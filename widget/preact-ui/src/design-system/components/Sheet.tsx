import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Sheet.module.css";

export interface SheetProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: ComponentChildren;
}

export const Sheet = ({ open, children }: SheetProps) => {
  // Don't lock body scroll - sheets are interactive and can be minimized
  // Unlike Dialog which blocks interaction, Sheet allows interaction with content behind it

  if (!open) return null;

  return <>{children}</>;
};

Sheet.displayName = "Sheet";

export interface SheetContentProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  children?: ComponentChildren;
  showHandle?: boolean;
  dismissible?: boolean;
  onToggle?: () => void;
  maxHeight?: string | number; // e.g., "80vh", "500px", 80 (interpreted as vh)
  shadow?: "sm" | "md" | "lg" | "xl" | "none";
}

export const SheetContent = forwardRef<HTMLDivElement, SheetContentProps>(
  (
    {
      className,
      children,
      showHandle = true,
      dismissible = false,
      onToggle,
      maxHeight = "80vh",
      shadow = "lg",
      style,
      ...props
    },
    ref
  ) => {
    const maxHeightValue = typeof maxHeight === "number" ? `${maxHeight}vh` : maxHeight;

    return (
      <div
        ref={ref}
        className={cm(styles.content, shadow && styles[`shadow-${shadow}`], className)}
        style={{ ...(style as any), maxHeight: maxHeightValue }}
        {...props}
      >
        {showHandle && (
          <div
            className={styles.dragHandle}
            onClick={onToggle}
            title={dismissible ? "Dismiss" : "Minimize/Expand"}
          >
            <div className={styles.dragHandleBar} />
          </div>
        )}
        {children}
      </div>
    );
  }
);

SheetContent.displayName = "SheetContent";

export const SheetHeader = forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.header, className)} {...props}>
        {children}
      </div>
    );
  }
);

SheetHeader.displayName = "SheetHeader";

export const SheetTitle = forwardRef<
  HTMLHeadingElement,
  preact.JSX.HTMLAttributes<HTMLHeadingElement>
>(({ className, children, ...props }, ref) => {
  return (
    <h2 ref={ref} className={cm(styles.title, className)} {...props}>
      {children}
    </h2>
  );
});

SheetTitle.displayName = "SheetTitle";

export const SheetDescription = forwardRef<
  HTMLParagraphElement,
  preact.JSX.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  return (
    <p ref={ref} className={cm(styles.description, className)} {...props}>
      {children}
    </p>
  );
});

SheetDescription.displayName = "SheetDescription";

export const SheetBody = forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.body, className)} {...props}>
        {children}
      </div>
    );
  }
);

SheetBody.displayName = "SheetBody";

export const SheetFooter = forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.footer, className)} {...props}>
        {children}
      </div>
    );
  }
);

SheetFooter.displayName = "SheetFooter";

export interface SheetCloseProps extends preact.JSX.HTMLAttributes<HTMLButtonElement> {}

export const SheetClose = forwardRef<HTMLButtonElement, SheetCloseProps>(
  ({ className, ...props }, ref) => {
    return (
      <button ref={ref} type="button" className={cm(styles.close, className)} {...props}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    );
  }
);

SheetClose.displayName = "SheetClose";
