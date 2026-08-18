import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Checkbox.module.css";

export interface CheckboxProps extends Omit<
  preact.JSX.HTMLAttributes<HTMLButtonElement>,
  "onChange"
> {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  disabled?: boolean;
  label?: ComponentChildren;
}

export const Checkbox = forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ className, checked = false, onChange, disabled, label, ...props }, ref) => {
    const handleClick = () => {
      if (!disabled && onChange) {
        onChange(!checked);
      }
    };

    return (
      <div className={cm(styles.checkbox, className)}>
        <button
          ref={ref}
          type="button"
          role="checkbox"
          aria-checked={checked}
          data-state={checked ? "checked" : "unchecked"}
          disabled={disabled}
          className={styles.checkboxRoot}
          onClick={handleClick}
          {...props}
        >
          {checked && (
            <svg
              className={styles.checkboxIndicator}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </button>
        {label && <span className={styles.label}>{label}</span>}
      </div>
    );
  }
);

Checkbox.displayName = "Checkbox";
