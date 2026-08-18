import { type ComponentChildren } from "preact";
import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Button.module.css";

export interface ButtonProps extends Omit<preact.JSX.HTMLAttributes<HTMLButtonElement>, "size"> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  size?: "sm" | "md" | "lg" | "icon";
  width?: "auto" | "full" | "fit";
  children?: ComponentChildren;
  asChild?: boolean;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "default",
      size = "md",
      width,
      className,
      children,
      disabled,
      type = "button",
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        className={cm(
          styles.button,
          styles[size],
          styles[variant],
          width && styles[`width-${width}`],
          className
        )}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
