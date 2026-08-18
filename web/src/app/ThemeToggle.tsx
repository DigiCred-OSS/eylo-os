import { Moon, Sun } from "lucide-react";
import { observer } from "mobx-react-lite";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";

const ThemeToggle = observer(function ThemeToggle() {
  const { theme } = useRootStore();
  const isDark = theme.resolvedTheme === "dark";
  const label = isDark ? "Use light theme" : "Use dark theme";

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={label}
      title={label}
      onClick={theme.toggle}
    >
      {isDark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  );
});

export { ThemeToggle };
