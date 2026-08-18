import { forwardRef } from "preact/compat";
import type { JSX, ComponentChildren } from "preact";
import { cm } from "../utils";
import styles from "./Field.module.css";

export interface FieldProps extends JSX.HTMLAttributes<HTMLDivElement> {
  label?: string;
  htmlFor?: string;
  required?: boolean;
  error?: string;
  description?: string;
  orientation?: "vertical" | "horizontal";
  children: ComponentChildren;
}

export const Field = forwardRef<HTMLDivElement, FieldProps>(
  (
    {
      className,
      label,
      htmlFor,
      required = false,
      error,
      description,
      orientation = "vertical",
      children,
      ...props
    },
    ref
  ) => {
    const hasError = !!error;

    return (
      <div
        ref={ref}
        className={cm(
          styles.field,
          orientation === "horizontal" && styles.fieldHorizontal,
          className
        )}
        {...props}
      >
        {label && (
          <label
            htmlFor={htmlFor}
            className={styles.fieldLabel}
            data-required={required}
            data-error={hasError}
          >
            {label}
          </label>
        )}

        <div className={styles.fieldContent}>
          {description && !hasError && <div className={styles.fieldDescription}>{description}</div>}

          {children}

          {hasError && (
            <div className={styles.fieldError} role="alert" aria-live="polite">
              <svg
                className={styles.fieldErrorIcon}
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }
);
