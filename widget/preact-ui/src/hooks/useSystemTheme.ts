import { useEffect, useState } from "preact/hooks";

/**
 * Hook to detect and respond to system color scheme preference
 * @returns 'dark' | 'light' based on system preference
 */
export function useSystemTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    // Check if running in browser
    if (typeof window === "undefined") return "light";

    // Check system preference
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "dark" : "light";
  });

  useEffect(() => {
    // Create media query
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    // Handler for theme changes
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      setTheme(e.matches ? "dark" : "light");
    };

    // Listen for changes
    mediaQuery.addEventListener("change", handleChange);

    // Initial check
    handleChange(mediaQuery);

    // Cleanup
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  return theme;
}

/**
 * Hook to apply system theme to widget root element
 */
export function useApplySystemTheme() {
  const theme = useSystemTheme();

  useEffect(() => {
    const widgetRoot = document.getElementById("eylo-widget");
    if (!widgetRoot) return;

    if (theme === "dark") {
      widgetRoot.classList.add("dark");
    } else {
      widgetRoot.classList.remove("dark");
    }
  }, [theme]);

  return theme;
}
