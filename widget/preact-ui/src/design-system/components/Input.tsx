import { forwardRef } from "preact/compat";
import { cm } from "../utils";
import styles from "./Input.module.css";

export interface InputProps extends preact.JSX.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  type?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", error, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cm(styles.input, error && styles.error, className)}
        {...props}
      />
    );
  }
);

Input.displayName = "Input";
