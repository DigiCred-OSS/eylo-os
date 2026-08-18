import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import type { LoginCredentials, Member } from "@/features/auth/auth.types";
import type { TokenStorage } from "@/features/auth/token-storage";

type SessionStatus = "anonymous" | "checking" | "authenticated" | "unavailable";

interface PendingHydration {
  accessToken: string;
  promise: Promise<void>;
}

const INVALID_CREDENTIALS_MESSAGE = "Email or password is incorrect.";
const LOGIN_FAILED_MESSAGE =
  "Could not sign in. Check your details and try again.";
const SESSION_UNAVAILABLE_MESSAGE =
  "Eylo could not verify this session. Check the API connection and try again.";

class AuthStore {
  accessToken: string | null;
  errorMessage: string | null = null;
  isSubmitting = false;
  member: Member | null = null;
  status: SessionStatus;

  private readonly api: ApiClient;
  private hydration: PendingHydration | null = null;
  private readonly storage: TokenStorage;

  constructor(api: ApiClient, storage: TokenStorage) {
    this.api = api;
    this.storage = storage;
    this.accessToken = storage.read();
    this.status = this.accessToken === null ? "anonymous" : "checking";

    makeAutoObservable<this, "api" | "hydration" | "storage">(
      this,
      {
        api: false,
        hydration: false,
        storage: false,
      },
      { autoBind: true },
    );

    storage.subscribe(this.syncAccessToken);
  }

  get organizationId(): string | null {
    return this.member?.organizationId ?? null;
  }

  expire(): void {
    this.storage.clear();
    this.accessToken = null;
    this.member = null;
    this.errorMessage = null;
    this.status = "anonymous";
  }

  hydrate(): Promise<void> {
    const accessToken = this.accessToken;
    if (accessToken === null) {
      this.status = "anonymous";
      return Promise.resolve();
    }

    if (this.status === "authenticated") {
      return Promise.resolve();
    }

    if (this.hydration?.accessToken === accessToken) {
      return this.hydration.promise;
    }

    this.status = "checking";
    this.errorMessage = null;
    const promise = this.loadMember(accessToken).finally(() => {
      runInAction(() => {
        if (this.hydration?.promise === promise) {
          this.hydration = null;
        }
      });
    });
    this.hydration = { accessToken, promise };

    return promise;
  }

  async login(credentials: LoginCredentials): Promise<void> {
    this.isSubmitting = true;
    this.errorMessage = null;

    try {
      const { data, response } = await this.api.POST("/api/auth/login", {
        body: credentials,
      });

      if (!response.ok || data === undefined) {
        throw new LoginError(
          response.status === 401
            ? INVALID_CREDENTIALS_MESSAGE
            : LOGIN_FAILED_MESSAGE,
        );
      }

      this.storage.write(data.accessToken);
      runInAction(() => {
        this.syncAccessToken(data.accessToken);
      });

      await this.hydrate();
    } catch (error) {
      runInAction(() => {
        if (this.status !== "unavailable") {
          this.errorMessage =
            error instanceof LoginError ? error.message : LOGIN_FAILED_MESSAGE;
        }
      });
    } finally {
      runInAction(() => {
        this.isSubmitting = false;
      });
    }
  }

  async logout(): Promise<void> {
    try {
      if (this.accessToken !== null) {
        await this.api.POST("/api/auth/logout");
      }
    } finally {
      runInAction(() => {
        this.expire();
      });
    }
  }

  private async loadMember(expectedAccessToken: string): Promise<void> {
    try {
      const { data, response } = await this.api.GET("/api/auth/me");

      if (response.status === 401) {
        runInAction(() => {
          if (this.accessToken === expectedAccessToken) {
            this.expire();
          }
        });
        return;
      }

      if (this.accessToken !== expectedAccessToken) {
        return;
      }

      if (!response.ok || data === undefined) {
        throw new Error("Session validation failed");
      }

      runInAction(() => {
        if (this.accessToken !== expectedAccessToken) {
          return;
        }
        this.member = data;
        this.errorMessage = null;
        this.status = "authenticated";
      });
    } catch {
      runInAction(() => {
        if (this.accessToken === expectedAccessToken) {
          this.member = null;
          this.errorMessage = SESSION_UNAVAILABLE_MESSAGE;
          this.status = "unavailable";
        }
      });
    }
  }

  private syncAccessToken(accessToken: string | null): void {
    if (accessToken === this.accessToken) {
      return;
    }

    this.accessToken = accessToken;
    this.member = null;
    this.errorMessage = null;
    this.status = accessToken === null ? "anonymous" : "checking";

    if (accessToken !== null) {
      void this.hydrate();
    }
  }
}

class LoginError extends Error {}

export { AuthStore };
export type { SessionStatus };
