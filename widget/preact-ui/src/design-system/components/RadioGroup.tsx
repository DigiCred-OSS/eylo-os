import { forwardRef } from "preact/compat";
import type { JSX } from "preact";
import { createContext } from "preact";
import { useContext } from "preact/hooks";
import { cm } from "../utils";
import styles from "./RadioGroup.module.css";

// Context to manage radio group state
interface RadioGroupContextValue {
  value?: string;
  onValueChange?: (value: string) => void;
  name: string;
  disabled?: boolean;
}

const RadioGroupContext = createContext<RadioGroupContextValue | null>(null);

const useRadioGroup = () => {
  const context = useContext(RadioGroupContext);
  if (!context) {
    throw new Error("RadioGroupItem must be used within RadioGroup");
  }
  return context;
};

// RadioGroup Component
export interface RadioGroupProps extends Omit<JSX.HTMLAttributes<HTMLDivElement>, "onChange"> {
  value?: string;
  onValueChange?: (value: string) => void;
  name?: string;
  orientation?: "vertical" | "horizontal";
  disabled?: boolean;
}

export const RadioGroup = forwardRef<HTMLDivElement, RadioGroupProps>(
  (
    {
      className,
      value,
      onValueChange,
      name = "radio-group",
      orientation = "vertical",
      disabled = false,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <RadioGroupContext.Provider value={{ value, onValueChange, name, disabled }}>
        <div
          ref={ref}
          role="radiogroup"
          className={cm(
            styles.radioGroup,
            orientation === "horizontal" && styles.radioGroupHorizontal,
            className
          )}
          {...props}
        >
          {children}
        </div>
      </RadioGroupContext.Provider>
    );
  }
);

// RadioGroupItem Component
export interface RadioGroupItemProps extends Omit<
  JSX.HTMLAttributes<HTMLLabelElement>,
  "onChange"
> {
  value: string;
  disabled?: boolean;
  label?: string;
  description?: string;
}

export const RadioGroupItem = forwardRef<HTMLLabelElement, RadioGroupItemProps>(
  ({ className, value, disabled: itemDisabled, label, description, children, ...props }, ref) => {
    const { value: groupValue, onValueChange, name, disabled: groupDisabled } = useRadioGroup();
    const isDisabled = itemDisabled || groupDisabled;
    const isChecked = groupValue === value;

    const handleChange = () => {
      if (!isDisabled && onValueChange) {
        onValueChange(value);
      }
    };

    return (
      <label
        ref={ref}
        className={cm(styles.radioItem, className)}
        data-disabled={isDisabled}
        {...props}
      >
        <input
          type="radio"
          name={name}
          value={value}
          checked={isChecked}
          disabled={isDisabled}
          onChange={handleChange}
          className={styles.radioInput}
          aria-describedby={description ? `${name}-${value}-description` : undefined}
        />
        <div className={styles.radioButton} />
        {(label || children) && (
          <div>
            <span className={styles.radioLabel}>{label || children}</span>
            {description && (
              <div id={`${name}-${value}-description`} className={styles.radioDescription}>
                {description}
              </div>
            )}
          </div>
        )}
      </label>
    );
  }
);
