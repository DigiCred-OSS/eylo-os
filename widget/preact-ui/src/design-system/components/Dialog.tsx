import { type ComponentChildren } from "preact";
import { forwardRef, useEffect } from "preact/compat";
import { cm } from "../utils";
import styles from "./Dialog.module.css";

export interface DialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: ComponentChildren;
}

export const Dialog = ({ open, onOpenChange, children }: DialogProps) => {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className={styles.overlay} onClick={() => onOpenChange?.(false)} />
      {children}
    </>
  );
};

Dialog.displayName = "Dialog";

export interface DialogContentProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  children?: ComponentChildren;
}

export const DialogContent = forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.content, className)} {...props}>
        {children}
      </div>
    );
  }
);

DialogContent.displayName = "DialogContent";

export const DialogHeader = forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.header, className)} {...props}>
        {children}
      </div>
    );
  }
);

DialogHeader.displayName = "DialogHeader";

export const DialogTitle = forwardRef<
  HTMLHeadingElement,
  preact.JSX.HTMLAttributes<HTMLHeadingElement>
>(({ className, children, ...props }, ref) => {
  return (
    <h2 ref={ref} className={cm(styles.title, className)} {...props}>
      {children}
    </h2>
  );
});

DialogTitle.displayName = "DialogTitle";

export const DialogDescription = forwardRef<
  HTMLParagraphElement,
  preact.JSX.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  return (
    <p ref={ref} className={cm(styles.description, className)} {...props}>
      {children}
    </p>
  );
});

DialogDescription.displayName = "DialogDescription";

export const DialogBody = forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.body, className)} {...props}>
        {children}
      </div>
    );
  }
);

DialogBody.displayName = "DialogBody";

export const DialogFooter = forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.footer, className)} {...props}>
        {children}
      </div>
    );
  }
);

DialogFooter.displayName = "DialogFooter";

export interface DialogCloseProps extends preact.JSX.HTMLAttributes<HTMLButtonElement> {}

export const DialogClose = forwardRef<HTMLButtonElement, DialogCloseProps>(
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

DialogClose.displayName = "DialogClose";
