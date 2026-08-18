import { makeAutoObservable } from "mobx";

type ThemePreference = "system" | "light" | "dark";
type ResolvedTheme = Exclude<ThemePreference, "system">;

const THEME_KEY = "eylo.console.theme";

class ThemeStore {
  preference: ThemePreference;
  systemTheme: ResolvedTheme;

  private readonly colorScheme: MediaQueryList;
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
    this.colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
    this.systemTheme = this.colorScheme.matches ? "dark" : "light";
    this.preference = readThemePreference(storage);

    makeAutoObservable<this, "colorScheme" | "storage">(
      this,
      { colorScheme: false, storage: false },
      { autoBind: true },
    );

    this.colorScheme.addEventListener("change", this.handleSystemThemeChange);
    this.apply();
  }

  get resolvedTheme(): ResolvedTheme {
    return this.preference === "system" ? this.systemTheme : this.preference;
  }

  toggle(): void {
    this.preference = this.resolvedTheme === "dark" ? "light" : "dark";
    try {
      this.storage.setItem(THEME_KEY, this.preference);
    } catch {
      // Theme persistence is optional; the selected theme still applies now.
    }
    this.apply();
  }

  private apply(): void {
    const isDark = this.resolvedTheme === "dark";
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
  }

  private handleSystemThemeChange(event: MediaQueryListEvent): void {
    this.systemTheme = event.matches ? "dark" : "light";

    if (this.preference === "system") {
      this.apply();
    }
  }
}

function readThemePreference(storage: Storage): ThemePreference {
  try {
    const storedPreference = storage.getItem(THEME_KEY);
    return storedPreference === "light" || storedPreference === "dark"
      ? storedPreference
      : "system";
  } catch {
    return "system";
  }
}

export { ThemeStore };
