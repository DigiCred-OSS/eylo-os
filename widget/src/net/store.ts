import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { EventEmitter, EYLO_EVENTS } from "@eylo/events";
import { ConnectionStateManager } from "@eylo/modules/conversation";
import { getServerWebSocketBaseUrl, logger } from "@eylo/utils";

import { WebSocketClient } from ".";
import type { EyloStore } from "../store/EyloStore";
import { WS_ACTIONS } from "./constants";
import {
  type TMessageHandler,
  type TWebSocketConfig,
  type TWsEventActionValue,
  type TWsMessage,
} from "./types";

const USER_SESSION_TAB_PROBE_MS = 75;

type TUserSessionTabMessage = {
  type: "probe" | "claim";
  nonce: string;
  userSessionId: string;
  tabId: string;
  startedAt: number;
};

export type TEyloConnectionState = {
  sessionId: string | null;
  userSessionId: string | null;
  connectionURL: string;
  isConnected?: boolean;
  identified?: boolean;
  error?: unknown;
};

class ConnectionStore extends BaseReactiveStore<TEyloConnectionState> {
  // @ts-ignore
  // the TS compiler does not recognize that _client will be initialized in the constructor
  private _client: WebSocketClient;
  private _parentStore: EyloStore;
  // @ts-ignore
  // ConnectionStateManager is initialized in __init__
  private _connectionStateManager: ConnectionStateManager;
  private _contactId: string | null = null;
  private _userSessionChannel: BroadcastChannel | null = null;
  private readonly _tabId = crypto.randomUUID();
  private readonly _tabStartedAt = performance.timeOrigin;

  constructor(parent: EyloStore) {
    const initialState = {
      sessionId: null,
      userSessionId: null,
      isConnected: false,
      identified: false,
      error: undefined,
    } as TEyloConnectionState;
    super(initialState, "eylo:connection:");
    this.computed(
      "connectionURL",
      () => {
        const connectionUrl = `${getServerWebSocketBaseUrl()}/${parent.organizationId}`;

        return connectionUrl;
      },
      []
    );
    this._parentStore = parent;
    this._setupUserSessionTabChannel();
    this.__init__();
  }

  private __init__ = (): void => {
    this._client = new WebSocketClient({
      url: this.get("connectionURL"),
      eventEmitter: this._parentStore.ee,
    } as TWebSocketConfig);
    this._setupEventListeners();
    this._initConnectionStateManager();
  };

  private userSessionStorageKey(organizationId: string, contactId: string): string {
    return `eylo:user-session:${organizationId}:${contactId}`;
  }

  private readPersistedUserSession(
    organizationId: string,
    contactId: string
  ): string | null {
    try {
      return globalThis.sessionStorage?.getItem(
        this.userSessionStorageKey(organizationId, contactId)
      ) ?? null;
    } catch {
      return null;
    }
  }

  private persistUserSession(userSessionId: string | null): void {
    if (this._contactId === null) {
      return;
    }
    try {
      const key = this.userSessionStorageKey(
        this._parentStore.organizationId,
        this._contactId
      );
      if (userSessionId) {
        globalThis.sessionStorage?.setItem(key, userSessionId);
      } else {
        globalThis.sessionStorage?.removeItem(key);
      }
    } catch {
      logger.warn("Browser session storage is unavailable; reconnect continuity is disabled.");
    }
  }

  private setContactScope(contactId: string | undefined): boolean {
    const normalized = contactId?.trim() || null;
    if (this._contactId === normalized) {
      return false;
    }
    this._contactId = normalized;
    const userSessionId = normalized
      ? this.readPersistedUserSession(this._parentStore.organizationId, normalized)
      : null;
    this.set("userSessionId", userSessionId);
    this._client.userSessionId = userSessionId;
    return true;
  }

  private _setupUserSessionTabChannel(): void {
    if (typeof BroadcastChannel === "undefined") {
      return;
    }
    const channel = new BroadcastChannel(
      `eylo:user-session-tabs:${this._parentStore.organizationId}`
    );
    channel.addEventListener("message", (event: MessageEvent<TUserSessionTabMessage>) => {
      const message = event.data;
      const userSessionId = this.get("userSessionId");
      if (
        message?.type !== "probe" ||
        !userSessionId ||
        message.userSessionId !== userSessionId
      ) {
        return;
      }
      channel.postMessage({
        type: "claim",
        nonce: message.nonce,
        userSessionId,
        tabId: this._tabId,
        startedAt: this._tabStartedAt,
      } satisfies TUserSessionTabMessage);
    });
    globalThis.addEventListener?.("pagehide", () => channel.close(), { once: true });
    this._userSessionChannel = channel;
  }

  private async _releaseCopiedUserSession(): Promise<void> {
    const userSessionId = this.get("userSessionId");
    const channel = this._userSessionChannel;
    if (!userSessionId || channel === null) {
      return;
    }

    const nonce = crypto.randomUUID();
    let claimedByOlderTab = false;
    const onClaim = (event: MessageEvent<TUserSessionTabMessage>): void => {
      const message = event.data;
      if (
        message?.type !== "claim" ||
        message.nonce !== nonce ||
        message.userSessionId !== userSessionId
      ) {
        return;
      }
      claimedByOlderTab ||=
        message.startedAt < this._tabStartedAt ||
        (message.startedAt === this._tabStartedAt && message.tabId < this._tabId);
    };
    channel.addEventListener("message", onClaim);
    channel.postMessage({
      type: "probe",
      nonce,
      userSessionId,
      tabId: this._tabId,
      startedAt: this._tabStartedAt,
    } satisfies TUserSessionTabMessage);
    await new Promise<void>((resolve) => {
      setTimeout(resolve, USER_SESSION_TAB_PROBE_MS);
    });
    channel.removeEventListener("message", onClaim);

    if (claimedByOlderTab && this.get("userSessionId") === userSessionId) {
      this.set("userSessionId", null);
      this._client.userSessionId = null;
      this.persistUserSession(null);
    }
  }

  private _initConnectionStateManager = (): void => {
    // Initialize ConnectionStateManager with dynamic sessionId getter
    this._connectionStateManager = new ConnectionStateManager(
      this._parentStore.organizationId,
      "/api",
      () => this.get("sessionId")
    );

    // Register WebSocket handlers for OAuth connection events
    this.registerMessageHandler("auth:required", (message: TWsMessage) => {
      logger.info("[AUTH_REQUIRED] Received event:", message);
      if (message.data) {
        const integrationId = message.data.integration_id || null;
        const vendor = message.data.vendor || null;
        if (!integrationId || !vendor) {
          logger.error("[AUTH_REQUIRED] Missing integration identity; ignoring event");
          return;
        }
        this._connectionStateManager.addAuthRequirement({
          id: `integration:${integrationId}`,
          integration_id: integrationId,
          vendor,
          auth_kind: message.data.auth_kind || null,
          integration_name: message.data.integration_name,
          reason: message.data.reason,
          contact_id: message.data.contact_id,
          conversation_id: message.data.conversation_id || null,
          message: message.data.message,
        });
      }
    });

    this.registerMessageHandler("connection:started", (message: TWsMessage) => {
      logger.info("[CONNECTION_STARTED] Received event:", message);
      if (message.data) {
        const auth = this._connectionStateManager
          .getPendingAuths()
          .find((candidate) => candidate.integration_id === message.data.integration_id);
        if (auth) {
          this._connectionStateManager.updateAuthStatus(auth.id, "connecting");
        }
      }
    });

    this.registerMessageHandler("connection:success", (message: TWsMessage) => {
      logger.info("[CONNECTION_SUCCESS] Received event:", message);
      if (message.data) {
        const auths = this._connectionStateManager.getPendingAuths();
        const auth = auths.find(
          (candidate) => candidate.integration_id === message.data.integration_id
        );
        if (auth) {
          this._connectionStateManager.updateAuthStatus(auth.id, "connected");
        }
      }
    });

    this.registerMessageHandler("connection:failed", (message: TWsMessage) => {
      logger.info("[CONNECTION_FAILED] Received event:", message);
      if (message.data) {
        const auths = this._connectionStateManager.getPendingAuths();
        const auth = auths.find(
          (candidate) => candidate.integration_id === message.data.integration_id
        );
        if (auth) {
          this._connectionStateManager.updateAuthStatus(
            auth.id,
            "failed",
            message.data.error || "Connection failed"
          );
        }
      }
    });
  };

  private _setupEventListeners = (): void => {
    const ee: EventEmitter = this._parentStore.ee;
    ee.on(EYLO_EVENTS.NET_CONNECTING, () => {
      this.set("isConnected", false);
      this.set("error", undefined);
      logger.debug("WebSocket is connecting...");
    });
    ee.on(EYLO_EVENTS.NET_CONNECTED, () => {
      this.set("isConnected", true);
      this.set("error", undefined);
      logger.debug("WebSocket is connected.");
    });
    ee.on(EYLO_EVENTS.NET_DISCONNECTED, () => {
      this.set("isConnected", false);
      this.set("identified", false);
      this.set("error", undefined);
      logger.debug("WebSocket is disconnected.");
    });
    ee.on(EYLO_EVENTS.CONTACT_IDENTIFIED, () => {
      this.set("identified", true);
      logger.debug("WS.IDENTIFIED contact associated with session.");
    });
    ee.on(EYLO_EVENTS.ERROR, (e: unknown) => {
      this.set("error", e);
      logger.error("WS.ERROR:", e);
    });
    this.registerMessageHandler(WS_ACTIONS.SESSION_INITIALIZED, (message: TWsMessage) => {
      const userSessionId = message.data?.user_session_id;
      if (typeof userSessionId !== "string" || !userSessionId) {
        logger.error("Session initialization response omitted user_session_id.");
        return;
      }
      this.set("userSessionId", userSessionId);
      this._client.userSessionId = userSessionId;
      this.persistUserSession(userSessionId);
    });
  };

  sendBinary = (data: ArrayBuffer): boolean => {
    if (this._client && this._client.isConnected) {
      return this._client.sendBinary(data);
    } else {
      logger.error("WebSocket is not connected. Cannot send binary data.");
      return false;
    }
  };

  send = (message: TWsMessage): boolean => {
    if (this._client && this._client.isConnected) {
      return this._client.send(message);
    } else {
      logger.error("WebSocket is not connected. Cannot send message.");
      return false;
    }
  };

  private _isValidEventAction(action: string | TWsEventActionValue): action is TWsEventActionValue {
    const validActions: TWsEventActionValue[] = Object.keys(WS_ACTIONS).map(
      (key) => WS_ACTIONS[key as keyof typeof WS_ACTIONS]
    );
    return validActions.includes(action as TWsEventActionValue);
  }

  // TODO: since this is a store, we can just synchronize the connection process
  // and session
  // on session null we can just disconnect
  // on session not null we can just connect
  // this way we can avoid multiple connections and disconnections
  public connectWithSession = async (
    sessionToken: string,
    contactId?: string
  ): Promise<void> => {
    const normalizedToken = sessionToken.trim();
    if (!normalizedToken) {
      throw new Error("Widget session token is required.");
    }
    const contactChanged = this.setContactScope(contactId);
    if (
      !contactChanged &&
      this.get("isConnected") &&
      this.get("sessionId") === normalizedToken
    ) {
      return;
    }

    await this._releaseCopiedUserSession();
    this.disconnect(1000, "transport_reinitialize", false);
    this._openSession(normalizedToken);
  };

  private _openSession = (sessionToken: string): void => {
    this.set("sessionId", sessionToken);
    this._client.initialize(sessionToken, this.get("userSessionId"));
  };

  public disconnect = (
    code: number = 1000,
    reason: string = "user_session_end",
    endUserSession: boolean = true
  ): void => {
    this._client.terminate(code, reason);
    this._connectionStateManager.reset();
    this.set("isConnected", false);
    this.set("identified", false);
    this.set("error", undefined);
    this.set("sessionId", null);
    if (endUserSession) {
      this.set("userSessionId", null);
      this._client.userSessionId = null;
      this.persistUserSession(null);
    }
  };

  /**
   * Get the ConnectionStateManager instance for managing OAuth connections
   */
  get connectionStateManager(): ConnectionStateManager {
    return this._connectionStateManager;
  }

  public registerMessageHandler = (action: TWsEventActionValue, handler: TMessageHandler): void => {
    if (!this._isValidEventAction(action)) {
      logger.warn(`Invalid action type: ${action}. Skipping.`);
      return;
    }
    if (typeof handler !== "function") {
      logger.warn(`Handler for action ${action} is not a function. Skipping.`);
      return;
    }
    if (this._client.messageHandlers[action]) {
      this._client.messageHandlers[action]!.push(handler);
    } else {
      this._client.messageHandlers[action] = [handler];
    }
  };

  public deregisterMessageHandler = (
    action: TWsEventActionValue,
    handler: TMessageHandler
  ): void => {
    if (!this._isValidEventAction(action)) {
      logger.warn(`Invalid action type: ${action}. Skipping.`);
      return;
    }
    if (typeof handler !== "function") {
      logger.warn(`Handler for action ${action} is not a function. Skipping.`);
      return;
    }
    const handlers = this._client.messageHandlers[action];
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
        logger.debug(`Handler for action ${action} deregistered.`);
      } else {
        logger.warn(`Handler for action ${action} not found.`);
      }
    } else {
      logger.warn(`No handlers registered for action ${action}.`);
    }
  };
}

export { ConnectionStore };
