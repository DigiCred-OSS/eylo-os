const ACCESS_TOKEN_KEY = "eylo.console.access-token";

type TokenStorageListener = (accessToken: string | null) => void;

interface TokenStorage {
  clear: () => void;
  read: () => string | null;
  subscribe: (listener: TokenStorageListener) => void;
  write: (accessToken: string) => void;
}

class BrowserTokenStorage implements TokenStorage {
  private readonly eventTarget: Window;
  private readonly storage: Storage;

  constructor(storage: Storage, eventTarget: Window) {
    this.storage = storage;
    this.eventTarget = eventTarget;
  }

  clear(): void {
    try {
      this.storage.removeItem(ACCESS_TOKEN_KEY);
    } catch {
      // The in-memory auth state still expires when persistence is unavailable.
    }
  }

  read(): string | null {
    try {
      return this.storage.getItem(ACCESS_TOKEN_KEY);
    } catch {
      return null;
    }
  }

  subscribe(listener: TokenStorageListener): void {
    this.eventTarget.addEventListener("storage", (event) => {
      if (
        event.storageArea === this.storage &&
        event.key === ACCESS_TOKEN_KEY
      ) {
        listener(event.newValue);
      }
    });
  }

  write(accessToken: string): void {
    try {
      this.storage.setItem(ACCESS_TOKEN_KEY, accessToken);
    } catch {
      // AuthStore keeps the token for this tab even without persistence.
    }
  }
}

export { BrowserTokenStorage };
export type { TokenStorage };
