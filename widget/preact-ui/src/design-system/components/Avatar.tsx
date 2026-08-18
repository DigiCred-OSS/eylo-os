import { type ComponentChildren } from "preact";
import { forwardRef, useState } from "preact/compat";
import { cm } from "../utils";
import styles from "./Avatar.module.css";

export interface AvatarProps extends preact.JSX.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "md" | "lg" | "xl";
  src?: string;
  alt?: string;
  fallback?: ComponentChildren;
  children?: ComponentChildren;
}

export const Avatar = forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, size = "md", src, alt, fallback, children, ...props }, ref) => {
    const [imageError, setImageError] = useState(false);

    return (
      <div ref={ref} className={cm(styles.avatar, styles[size], className)} {...props}>
        {src && !imageError ? (
          <img
            src={src}
            alt={alt || "Avatar"}
            className={styles.image}
            onError={() => setImageError(true)}
          />
        ) : (
          <div className={styles.fallback}>
            {fallback || children || alt?.charAt(0).toUpperCase()}
          </div>
        )}
      </div>
    );
  }
);

Avatar.displayName = "Avatar";
