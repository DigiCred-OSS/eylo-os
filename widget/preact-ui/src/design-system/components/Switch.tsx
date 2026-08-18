import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Switch.module.css";

export interface SwitchProps extends Omit<
  preact.JSX.HTMLAttributes<HTMLButtonElement>,
  "onChange"
> {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  disabled?: boolean;
  label?: ComponentChildren;
}

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(
  ({ className, checked = false, onChange, disabled, label, ...props }, ref) => {
    const handleClick = () => {
      if (!disabled && onChange) {
        onChange(!checked);
      }
    };

    return (
      <div className={cm(styles.switch, className)}>
        <button
          ref={ref}
          type="button"
          role="switch"
          aria-checked={checked}
          data-state={checked ? "checked" : "unchecked"}
          disabled={disabled}
          className={styles.switchRoot}
          onClick={handleClick}
          {...props}
        >
          <span className={styles.switchThumb} />
        </button>
        {label && <span className={styles.label}>{label}</span>}
      </div>
    );
  }
);

Switch.displayName = "Switch";
