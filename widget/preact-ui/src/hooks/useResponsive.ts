// hooks/useResponsive.ts
import { useEffect, useState } from "preact/hooks";

/**
 * Hook to detect mobile screen size
 */
export function useResponsive(breakpoint: number = 480) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < breakpoint);
    };

    checkMobile();
    window.addEventListener("resize", checkMobile);

    return () => {
      window.removeEventListener("resize", checkMobile);
    };
  }, [breakpoint]);

  return { isMobile };
}
