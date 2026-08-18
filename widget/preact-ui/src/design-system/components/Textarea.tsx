import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Textarea.module.css";

export interface TextareaProps extends preact.JSX.HTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  disabled?: boolean;
  rows?: number;
  cols?: number;
  /** Minimum height variant */
  minHeight?: "sm" | "md" | "lg" | "xl" | "2xl";
  /** Maximum height variant */
  maxHeight?: "sm" | "md" | "lg" | "xl" | "2xl" | "none";
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, minHeight, maxHeight, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cm(
          styles.textarea,
          error && styles.error,
          minHeight && styles[`minHeight-${minHeight}`],
          maxHeight && styles[`maxHeight-${maxHeight}`],
          className
        )}
        {...props}
      />
    );
  }
);

Textarea.displayName = "Textarea";
