/**
 * OAuth connection management for conversations
 * Handles tracking pending authentication requests and OAuth popup flows
 */

import { getServerBaseUrl } from "../../utils/http";

interface OAuthRedirect {
  authorizationUrl: string;
  callbackOrigin?: string;
}

type OAuthPostMessage =
  {
      type: "eylo:curated-oauth";
      ok: boolean;
      connectionId?: string | null;
      vendor?: string | null;
      error?: string | null;
    };

export type CuratedCredentialInput = {
  apiKey?: string;
  username?: string;
  password?: string;
};

export interface AuthRequirement {
  id: string;
  integration_id: string;
  vendor: string;
  auth_kind: "oauth2" | "api_key" | "basic" | "no_auth" | null;
  integration_name: string;
  reason: string;
  contact_id: string | null;
  conversation_id: string | null;
  message: string;
  status: "pending" | "connecting" | "connected" | "dismissed" | "failed";
  timestamp: number;
  error?: string;
}

export type AuthRequirementCallback = (requirement: AuthRequirement | null) => void;

function requireHttpUrl(value: unknown, fieldName: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`OAuth response is missing ${fieldName}`);
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`OAuth response contains an invalid ${fieldName}`);
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error(`OAuth response contains an invalid ${fieldName}`);
  }
  return value;
}

function decodeOAuthRedirect(payload: unknown): OAuthRedirect {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    throw new Error("OAuth response is invalid");
  }

  const response = payload as Record<string, unknown>;
  const authorizationUrl = requireHttpUrl(
    response.authorizationUrl,
    "authorization URL"
  );
  return {
    authorizationUrl,
    callbackOrigin: requireHttpUrl(response.callbackOrigin, "callback origin"),
  };
}

export class ConnectionStateManager {
  private organizationId: string;
  private baseUrl: string;
  private getSessionId: () => string | null;
  private pendingAuths: Map<string, AuthRequirement>;
  private listeners: Set<AuthRequirementCallback>;
  private activePopupIntegrationId: string | null = null;

  constructor(
    organizationId: string,
    baseUrl: string = "/api/v1",
    getSessionId: (() => string | null) | string | null = null
  ) {
    this.organizationId = organizationId;
    this.baseUrl = baseUrl;
    // Support both function and static value for backwards compatibility
    this.getSessionId = typeof getSessionId === "function" ? getSessionId : () => getSessionId;
    this.pendingAuths = new Map();
    this.listeners = new Set();
  }

  /**
   * Add a new auth requirement from AUTH_REQUIRED event
   */
  addAuthRequirement(requirement: Omit<AuthRequirement, "status" | "timestamp">): void {
    const authReq: AuthRequirement = {
      ...requirement,
      status: "pending",
      timestamp: Date.now(),
    };

    this.pendingAuths.set(requirement.id, authReq);
    this.notifyListeners();
  }

  /**
   * Update status of an auth requirement
   */
  updateAuthStatus(requirementId: string, status: AuthRequirement["status"], error?: string): void {
    const auth = this.pendingAuths.get(requirementId);
    if (auth) {
      auth.status = status;
      if (error) {
        auth.error = error;
      } else if (status !== "failed") {
        // Clear error if moving away from failed state
        auth.error = undefined;
      }
      this.notifyListeners();

      // Remove from pending if connected or dismissed
      if (status === "connected" || status === "dismissed") {
        setTimeout(() => {
          this.pendingAuths.delete(requirementId);
          this.notifyListeners();
        }, 500); // Small delay for UI feedback
      }
    }
  }

  /**
   * Get all pending auth requirements (including failed ones that can be retried)
   */
  getPendingAuths(): AuthRequirement[] {
    return Array.from(this.pendingAuths.values()).filter(
      (auth) =>
        auth.status === "pending" || auth.status === "connecting" || auth.status === "failed"
    );
  }

  /**
   * Dismiss an auth requirement
   */
  dismissAuth(requirementId: string): void {
    this.updateAuthStatus(requirementId, "dismissed");
  }

  /**
   * Retry a failed auth requirement
   */
  retryAuth(requirementId: string): void {
    const auth = this.pendingAuths.get(requirementId);
    if (auth && auth.status === "failed") {
      auth.status = "pending";
      auth.error = undefined;
      this.notifyListeners();
    }
  }

  /**
   * Open OAuth popup for an auth requirement
   * Backend generates the complete OAuth URL with proper redirect_uri
   * Uses session-authenticated widget endpoint
   */
  async openOAuthPopup(requirementId: string): Promise<void> {
    // Prevent concurrent OAuth popups
    if (this.activePopupIntegrationId) {
      throw new Error("Another OAuth flow is already in progress");
    }
    this.activePopupIntegrationId = requirementId;

    const auth = this.pendingAuths.get(requirementId);
    if (!auth) {
      this.activePopupIntegrationId = null;
      throw new Error("Invalid auth requirement");
    }
    if (auth.auth_kind !== "oauth2") {
      this.activePopupIntegrationId = null;
      throw new Error("This connection does not use OAuth");
    }
    if (!auth.conversation_id) {
      this.activePopupIntegrationId = null;
      throw new Error("The connection request is missing its conversation context");
    }

    const sessionId = this.getSessionId();
    if (!sessionId) {
      throw new Error("Session ID not available");
    }

    this.updateAuthStatus(requirementId, "connecting");

    try {
      // Fetch the OAuth URL from the widget endpoint with proper X-Session-ID header
      const serverBaseUrl = getServerBaseUrl();
      const apiUrl = `${serverBaseUrl}${this.baseUrl}/widget/${this.organizationId}/curated-connections/oauth/initiate?vendor=${encodeURIComponent(auth.vendor)}&conversation_id=${encodeURIComponent(auth.conversation_id)}`;

      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          "X-Session-ID": sessionId,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to get OAuth URL: ${response.statusText}`);
      }

      const redirect = decodeOAuthRedirect(await response.json());

      // Now open the OAuth provider's URL in a popup
      const result = await openOAuthPopup(redirect.authorizationUrl, redirect.callbackOrigin);
      if (result.vendor && result.vendor !== auth.vendor) {
        throw new Error("OAuth callback did not match the requested vendor");
      }
      this.activePopupIntegrationId = null;
      this.updateAuthStatus(requirementId, "connected");
    } catch (error) {
      this.activePopupIntegrationId = null;
      const errorMsg = error instanceof Error ? error.message : "Connection failed";
      const updatedAuth = this.pendingAuths.get(requirementId);
      if (updatedAuth) {
        updatedAuth.status = "failed";
        updatedAuth.error = errorMsg;
        this.notifyListeners();
      }
      throw error;
    }
  }

  /** Bind a direct API key or basic credential to the current widget contact. */
  async connectWithCredentials(
    requirementId: string,
    credentials: CuratedCredentialInput
  ): Promise<void> {
    const auth = this.pendingAuths.get(requirementId);
    if (
      !auth ||
      (auth.auth_kind !== "api_key" && auth.auth_kind !== "basic")
    ) {
      throw new Error("This connection does not accept direct credentials");
    }
    if (!auth.conversation_id) {
      throw new Error("The connection request is missing its conversation context");
    }
    const sessionId = this.getSessionId();
    if (!sessionId) {
      throw new Error("Session ID not available");
    }

    this.updateAuthStatus(requirementId, "connecting");
    try {
      const serverBaseUrl = getServerBaseUrl();
      const response = await fetch(
        `${serverBaseUrl}${this.baseUrl}/widget/${this.organizationId}/curated-connections/${encodeURIComponent(auth.vendor)}/connect?conversation_id=${encodeURIComponent(auth.conversation_id)}`,
        {
          method: "POST",
          headers: {
            "X-Session-ID": sessionId,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(credentials),
        }
      );
      if (!response.ok) {
        throw new Error(`Connection failed: ${response.statusText}`);
      }
      this.updateAuthStatus(requirementId, "connected");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Connection failed";
      this.updateAuthStatus(requirementId, "failed", message);
      throw error;
    }
  }

  /**
   * Reset all state — call on disconnect to prevent stale data
   */
  reset(): void {
    this.pendingAuths.clear();
    this.activePopupIntegrationId = null;
    this.notifyListeners();
  }

  /**
   * Subscribe to auth requirement changes
   */
  subscribe(callback: AuthRequirementCallback): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Notify all listeners of state change
   */
  private notifyListeners(): void {
    this.listeners.forEach((callback) => callback(null));
  }
}

/**
 * Open OAuth popup from direct URL
 * Returns a promise that resolves when connection succeeds or rejects on failure
 */
export function openOAuthPopup(
  url: string,
  trustedCallbackOrigin?: string
): Promise<{ connectionId: string; integrationName: string; vendor?: string }> {
  return new Promise((resolve, reject) => {
    const popup = window.open(url, "oauth_popup", "width=600,height=700,left=200,top=100");

    if (!popup) {
      reject(new Error("Popup blocked. Please allow popups for this site."));
      return;
    }

    // Listen for postMessage from the OAuth callback
    const expectedOrigin = new URL(
      trustedCallbackOrigin || getServerBaseUrl() || window.location.origin,
      window.location.origin
    ).origin;
    const messageHandler = (event: MessageEvent) => {
      if (event.origin !== expectedOrigin) return;

      const data = event.data as OAuthPostMessage;
      if (data.type === "eylo:curated-oauth") {
        window.removeEventListener("message", messageHandler);
        clearInterval(pollTimer);
        if (!data.ok) {
          reject(new Error(data.error || "Connection failed"));
          return;
        }
        resolve({
          connectionId: data.connectionId || "",
          integrationName: data.vendor || "Integration",
          vendor: data.vendor || undefined,
        });
      }
    };

    window.addEventListener("message", messageHandler);

    // Poll to detect if user closed popup
    const pollTimer = setInterval(() => {
      if (popup.closed) {
        clearInterval(pollTimer);
        window.removeEventListener("message", messageHandler);
        reject(new Error("OAuth popup was closed"));
      }
    }, 1000);
  });
}
