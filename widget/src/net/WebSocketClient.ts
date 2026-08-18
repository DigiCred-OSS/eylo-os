import { EventEmitter, EYLO_EVENTS } from "@eylo/events";
import { logger } from "@eylo/utils";

import { WS_ACTIONS } from "./constants";
import type { TMessageHandlerMap, TRetryOptions, TWebSocketConfig, TWsMessage } from "./types";

const DEFAULT_RETRY_OPTIONS: TRetryOptions = {
  maxRetries: 5,
  initialDelay: 1000, // 1 second
  maxDelay: 30000, // 30 seconds
  backoffMultiplier: 2,
};

const WS_CLOSE_CODE_NORMAL = 1000;
const WS_CLOSE_CODE_ERROR = 1006; // Abnormal closure
const DEFAULT_PING_INTERVAL = 5000; // 5 seconds
const DEFAULT_PONG_TIMEOUT = 10000; // 10 seconds

export class WebSocketClient {
  private _requestQueue: Map<string, TWsMessage> = new Map();
  private _ws: WebSocket | null = null;
  private _wsConfig: TWebSocketConfig;
  // Ping and Pong handling
  private _pingTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private _maxPingMissTolerance: number = 3;
  private _pingMissCount: number = 0;
  private _maxRoundTripTime: number = 5000; // 5 seconds
  private _messageHandlers: TMessageHandlerMap = {};
  // Auto-reconnect handling
  private _shouldAutoReconnect: boolean = true;
  private _retryCount: number = 0;
  private _retryTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private _isRetrying: boolean = false;
  private _ee: EventEmitter;
  private _sessionId: string | null = null;
  private _userSessionId: string | null = null;

  constructor(config: TWebSocketConfig) {
    this._wsConfig = config;
    this._wsConfig.retryOptions = {
      ...DEFAULT_RETRY_OPTIONS,
      ...config.retryOptions,
    };
    this._wsConfig.pingInterval = config.pingInterval || DEFAULT_PING_INTERVAL;
    this._wsConfig.pongTimeout = config.pongTimeout || DEFAULT_PONG_TIMEOUT;
    this._ee = this._wsConfig.eventEmitter;
  }

  private _isConnected(): boolean {
    return this._ws !== null && this._ws.readyState === WebSocket.OPEN;
  }
  private _isConnecting(): boolean {
    return this._ws !== null && this._ws.readyState === WebSocket.CONNECTING;
  }

  private _cleanupConnection = (): void => {
    if (this._ws) {
      logger.debug("Closing existing WebSocket connection before initializing a new one.");
      const ws = this._ws;
      this._ws.onclose = null; // Clear existing onclose handler
      this._ws.onmessage = null; // Clear existing onmessage handler
      this._ws.onerror = null; // Clear existing onerror handler
      this._ws.onopen = null; // Clear existing onopen handler
      this._ws = null;
      ws.close(WS_CLOSE_CODE_NORMAL, "Reinitializing WebSocket");
    }
  };
  public initialize = (sessionId: string, userSessionId: string | null = null): void => {
    this._sessionId = sessionId;
    this._userSessionId = userSessionId;
    this._shouldAutoReconnect = true;
    if (this._isConnected() || this._isConnecting()) {
      logger.debug("WebSocket is already connected or connecting.");
      return;
    }
    this._cleanupConnection();
    const url = new URL(`${this._wsConfig.url}/${sessionId}`);
    if (userSessionId) {
      url.searchParams.set("user_session_id", userSessionId);
    }
    this._ws = new WebSocket(url.toString(), this._wsConfig.protocols);
    this._setupWsEventListeners();
    this._setupDefaultMessageHandlers();
    logger.debug("WebSocket initialized:", {
      url: url.toString(),
      protocols: this._wsConfig.protocols,
    });
    this._ee.emit(EYLO_EVENTS.NET_CONNECTING);
  };

  public terminate = (
    code: number = WS_CLOSE_CODE_NORMAL,
    reason: string = "Normal closure"
  ): void => {
    this._shouldAutoReconnect = false;
    const ws = this._ws;
    this._ws = null;
    if (ws && ws.readyState <= WebSocket.OPEN) {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      ws.close(code, reason);
    }
    this._cleanupTimers();
    logger.debug("WebSocket terminated:", { code, reason });
  };

  private _setupWsEventListeners = (): void => {
    if (!this._ws) {
      throw new Error("WebSocket is not initialized.");
    }
    this._ws.onopen = () => {
      this._setupKeepAlive();
      this._retryCount = 0; // Reset retry count on successful connection
      this._isRetrying = false;
      logger.debug("WebSocket connection established.");
      this._ee.emit(EYLO_EVENTS.NET_CONNECTED);
    };

    this._ws.onmessage = (event: MessageEvent) => {
      try {
        const message: TWsMessage = JSON.parse(event.data);
        // dequeue the request if it has a requestId
        if (message.requestId) {
          this._requestQueue.delete(message.requestId);
        }
        logger.debug("WebSocket message received", {
          kind: message.kind,
          requestId: message.requestId,
          size: typeof event.data === "string" ? event.data.length : undefined,
        });
        this._handleMessage(message).catch((error) => {
          logger.error("Error handling WebSocket message:", error);
        });
      } catch (error) {
        logger.error("Error parsing WebSocket message:", error);
      }
    };

    this._ws.onerror = (error: Event) => {
      logger.error("WebSocket error:", error);
    };

    this._ws.onclose = (event: CloseEvent) => {
      logger.debug("WebSocket closed:", event);
      if (event.code !== WS_CLOSE_CODE_NORMAL && this._shouldAutoReconnect) {
        logger.warn("WebSocket closed abnormally. Attempting to reconnect...");
        this._retryConnection();
      }
      this._ee.emit(EYLO_EVENTS.NET_DISCONNECTED);
    };
  };

  private _retryConnection = (): void => {
    if (!this._shouldAutoReconnect || this._isRetrying) {
      logger.debug("Auto-reconnect is disabled or already retrying. Skipping retry.");
      return;
    }
    const retryOptions = this._wsConfig.retryOptions;
    if (!retryOptions) {
      throw new Error("Retry options are not configured.");
    }
    this._isRetrying = true;
    this._retryCount++;
    const delay = Math.min(
      retryOptions.initialDelay * Math.pow(retryOptions.backoffMultiplier, this._retryCount - 1),
      retryOptions.maxDelay
    );
    logger.debug(`Retrying WebSocket connection in ${delay} ms (attempt ${this._retryCount})...`);
    if (this._retryCount > retryOptions.maxRetries) {
      logger.error(`Max retry attempts (${retryOptions.maxRetries}) reached. Giving up.`);
      this.terminate(WS_CLOSE_CODE_ERROR, "Max retry attempts reached");
      return;
    }
    this._retryTimeoutId = setTimeout(() => {
      this._isRetrying = false;
      this.initialize(this._sessionId!, this._userSessionId);
    }, delay);
  };

  private _setupKeepAlive = (): void => {
    this._pingTimeoutId = setTimeout(() => {
      if (this._isConnected()) {
        const pingPacket: TWsMessage = {
          kind: WS_ACTIONS.PING,
          timestamp: Date.now(),
        };
        this.send(pingPacket);
        this._setupKeepAlive();
      }
    }, this._wsConfig.pingInterval);
  };

  public sendBinary = (data: ArrayBuffer): boolean => {
    if (!this._ws) {
      throw new Error("WebSocket is not initialized.");
    }
    if (this._isConnected()) {
      this._ws.send(data);
      return true;
    }
    return false;
  };

  public send = (message: TWsMessage): boolean => {
    if (!this._ws) {
      throw new Error("WebSocket is not initialized.");
    }
    if (message.requestId && this._requestQueue.has(message.requestId)) {
      logger.warn(`Message with requestId ${message.requestId} already exists in the queue.`);
      return false;
    }
    if (this._isConnected()) {
      if (!message.requestId) {
        message.requestId = crypto.randomUUID();
      }
      if (!message.timestamp) {
        message.timestamp = Date.now();
      }
      const payload = JSON.stringify(message);
      logger.debug("WebSocket message sent", {
        kind: message.kind,
        requestId: message.requestId,
        size: payload.length,
      });
      this._ws.send(payload);
      this._requestQueue.set(message.requestId, message);
      return true;
    }
    return false;
  };

  _handlePong = async (message: TWsMessage): Promise<void> => {
    if (message.kind !== WS_ACTIONS.PONG) {
      return;
    }
    const { server_time } = message.data || {};
    if (!server_time) {
      logger.warn("Pong message missing server_time:", message);
      return;
    }
    const timeDifference = Date.now() - server_time * 1000;
    if (timeDifference > this._maxRoundTripTime) {
      this._pingMissCount++;
    }
    if (this._pingMissCount >= this._maxPingMissTolerance) {
      logger.warn(`Ping miss count exceeded (${this._pingMissCount}). Disconnecting...`);
      this.terminate(WS_CLOSE_CODE_ERROR, "Ping miss count exceeded");
    }
  };

  _handlePing = (message: TWsMessage): void => {
    if (message.kind !== WS_ACTIONS.PING) {
      return;
    }
    const pongPacket: TWsMessage = {
      kind: WS_ACTIONS.PONG,
      timestamp: Date.now(),
      requestId: message.requestId,
    };
    this.send(pongPacket);
  };

  _handleError = (message: TWsMessage): void => {
    if (message.kind !== WS_ACTIONS.ERROR) {
      return;
    }

    const errorPacket = {
      kind: WS_ACTIONS.ERROR,
      timestamp: Date.now(),
      requestId: message.requestId,
      data: message.data,
    };

    logger.error("WebSocket error:", errorPacket);
    this._ee.emit(EYLO_EVENTS.ERROR, errorPacket);
  };

  _handleMessage = async (message: TWsMessage): Promise<void> => {
    // Reset ping miss count on any message received
    this._pingMissCount = 0;
    this._shouldAutoReconnect = true;
    if (!message || !message.kind) {
      logger.warn("Received invalid message:\n", message);
      return;
    }
    const handlers = this._messageHandlers[message.kind as keyof TMessageHandlerMap];
    if (!handlers || handlers.length === 0) {
      logger.warn(`No handlers for message kind: ${message.kind}`);
      return;
    }
    for (const handler of handlers) {
      try {
        const result = handler(message);
        if (result instanceof Promise) {
          try {
            await result;
          } catch (error) {
            logger.error(`Error in async message handler for ${message.kind}:`, message, error);
          }
        }
      } catch (error) {
        logger.error(`Error in message handler for ${message.kind}:`, message, error);
      }
    }
  };

  get isConnected(): boolean {
    return this._isConnected();
  }

  get messageHandlers(): TMessageHandlerMap {
    return this._messageHandlers;
  }

  public set userSessionId(userSessionId: string | null) {
    this._userSessionId = userSessionId;
  }

  set messageHandlers(handlers: TMessageHandlerMap) {
    this._messageHandlers = {
      ...this._messageHandlers,
      ...handlers,
    };
  }

  private _setupDefaultMessageHandlers(): void {
    this.messageHandlers = {
      ...this.messageHandlers,
      [WS_ACTIONS.PING]: [this._handlePing.bind(this)],
      [WS_ACTIONS.PONG]: [this._handlePong.bind(this)],
      [WS_ACTIONS.ERROR]: [this._handleError.bind(this)],
    };
  }

  private _cleanupTimers = (): void => {
    if (this._pingTimeoutId) {
      clearTimeout(this._pingTimeoutId);
      this._pingTimeoutId = null;
    }
    if (this._retryTimeoutId) {
      clearTimeout(this._retryTimeoutId);
      this._retryTimeoutId = null;
    }
  };
}
