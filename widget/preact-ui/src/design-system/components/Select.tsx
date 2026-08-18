import { forwardRef } from "preact/compat";
import type { JSX } from "preact";
import { createContext } from "preact";
import { useContext, useState, useEffect, useRef } from "preact/hooks";
import { cm } from "../utils";
import styles from "./Select.module.css";

// Context for Select state
interface SelectContextValue {
  value?: string;
  onValueChange?: (value: string) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
  searchValue: string;
  setSearchValue: (value: string) => void;
  disabled?: boolean;
}

const SelectContext = createContext<SelectContextValue | null>(null);

const useSelect = () => {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error("Select components must be used within Select");
  }
  return context;
};

// Select Root Component
export interface SelectProps extends Omit<JSX.HTMLAttributes<HTMLDivElement>, "onChange"> {
  value?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
  defaultOpen?: boolean;
}

export const Select = forwardRef<HTMLDivElement, SelectProps>(
  (
    { className, value, onValueChange, disabled = false, defaultOpen = false, children, ...props },
    ref
  ) => {
    const [open, setOpen] = useState(defaultOpen);
    const [searchValue, setSearchValue] = useState("");

    // Close dropdown when clicking outside
    const wrapperRef = (ref as any) || useRef<HTMLDivElement>(null);
    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
          setOpen(false);
          setSearchValue("");
        }
      };

      if (open) {
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
      }
    }, [open]);

    return (
      <SelectContext.Provider
        value={{ value, onValueChange, open, setOpen, searchValue, setSearchValue, disabled }}
      >
        <div ref={wrapperRef} className={cm(styles.selectWrapper, className)} {...props}>
          {children}
        </div>
      </SelectContext.Provider>
    );
  }
);

// SelectTrigger Component
export interface SelectTriggerProps extends JSX.HTMLAttributes<HTMLButtonElement> {
  error?: boolean;
  placeholder?: string;
}

export const SelectTrigger = forwardRef<HTMLButtonElement, SelectTriggerProps>(
  ({ className, error, placeholder = "Select...", children, ...props }, ref) => {
    const { value, open, setOpen, disabled } = useSelect();

    return (
      <button
        ref={ref}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => !disabled && setOpen(!open)}
        className={cm(styles.selectTrigger, className)}
        data-open={open}
        data-disabled={disabled}
        data-error={error}
        {...props}
      >
        <span className={cm(styles.selectValue, !value && styles.selectPlaceholder)}>
          {children || placeholder}
        </span>
        <svg
          className={styles.selectIcon}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
    );
  }
);

// SelectContent Component
export interface SelectContentProps extends JSX.HTMLAttributes<HTMLDivElement> {
  position?: "top" | "bottom";
  searchable?: boolean;
  searchPlaceholder?: string;
}

export const SelectContent = forwardRef<HTMLDivElement, SelectContentProps>(
  (
    {
      className,
      position = "bottom",
      searchable = false,
      searchPlaceholder = "Search...",
      children,
      ...props
    },
    ref
  ) => {
    const { open, searchValue, setSearchValue } = useSelect();

    if (!open) return null;

    return (
      <div
        ref={ref}
        role="listbox"
        className={cm(styles.selectContent, className)}
        data-position={position}
        {...props}
      >
        {searchable && (
          <input
            type="text"
            className={styles.selectSearch}
            placeholder={searchPlaceholder}
            value={searchValue}
            onInput={(e) => setSearchValue((e.target as HTMLInputElement).value)}
            onClick={(e) => e.stopPropagation()}
          />
        )}
        <div className={styles.selectList}>{children}</div>
      </div>
    );
  }
);

// SelectItem Component
export interface SelectItemProps extends JSX.HTMLAttributes<HTMLDivElement> {
  value: string;
  disabled?: boolean;
}

export const SelectItem = forwardRef<HTMLDivElement, SelectItemProps>(
  ({ className, value, disabled = false, children, ...props }, ref) => {
    const {
      value: selectedValue,
      onValueChange,
      setOpen,
      setSearchValue,
      searchValue,
    } = useSelect();
    const isSelected = selectedValue === value;

    // Filter based on search
    const childText = typeof children === "string" ? children : value;
    const matchesSearch =
      !searchValue || childText.toLowerCase().includes(searchValue.toLowerCase());

    if (!matchesSearch) return null;

    const handleSelect = () => {
      if (!disabled && onValueChange) {
        onValueChange(value);
        setOpen(false);
        setSearchValue("");
      }
    };

    return (
      <div
        ref={ref}
        role="option"
        aria-selected={isSelected}
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : 0}
        onClick={handleSelect}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleSelect();
          }
        }}
        className={cm(styles.selectItem, className)}
        data-selected={isSelected}
        data-disabled={disabled}
        {...props}
      >
        <span className={styles.selectItemIndicator}>
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
        </span>
        {children}
      </div>
    );
  }
);

// SelectValue Component (displays selected value)
export interface SelectValueProps {
  placeholder?: string;
}

export const SelectValue = ({ placeholder = "Select..." }: SelectValueProps) => {
  const { value } = useSelect();
  return <>{value || placeholder}</>;
};

// SelectEmpty Component
export interface SelectEmptyProps extends JSX.HTMLAttributes<HTMLDivElement> {}

export const SelectEmpty = forwardRef<HTMLDivElement, SelectEmptyProps>(
  ({ className, children = "No results found", ...props }, ref) => {
    const { searchValue } = useSelect();

    if (!searchValue) return null;

    return (
      <div ref={ref} className={cm(styles.selectEmpty, className)} {...props}>
        {children}
      </div>
    );
  }
);

// SelectGroup Component
export interface SelectGroupProps extends JSX.HTMLAttributes<HTMLDivElement> {}

export const SelectGroup = forwardRef<HTMLDivElement, SelectGroupProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} role="group" className={cm(styles.selectGroup, className)} {...props}>
        {children}
      </div>
    );
  }
);

// SelectGroupLabel Component
export interface SelectGroupLabelProps extends JSX.HTMLAttributes<HTMLDivElement> {}

export const SelectGroupLabel = forwardRef<HTMLDivElement, SelectGroupLabelProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cm(styles.selectGroupLabel, className)} {...props}>
        {children}
      </div>
    );
  }
);

// SelectSeparator Component
export interface SelectSeparatorProps extends JSX.HTMLAttributes<HTMLDivElement> {}

export const SelectSeparator = forwardRef<HTMLDivElement, SelectSeparatorProps>(
  ({ className, ...props }, ref) => {
    return <div ref={ref} className={cm(styles.selectSeparator, className)} {...props} />;
  }
);
