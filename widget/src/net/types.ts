// WebSocket Client Types

import type { EventEmitter } from "@eylo/events";

import type { WS_ACTIONS } from "./constants";

export type TWsEventAction = keyof typeof WS_ACTIONS;
export type TWsEventActionValue = (typeof WS_ACTIONS)[keyof typeof WS_ACTIONS];

export type TWsMessage = {
  kind: TWsEventActionValue;
  data?: any;
  timestamp?: number;
  requestId?: string;
};

export type TWsResponse = {
  status: number; // HTTP status code
  kind: TWsEventActionValue;
  organizationId: string; // UUID as string
  sessionId: string; // UUID as string
  requestId?: string;
  timestamp: number; // Unix timestamp in milliseconds
  data?: Record<string, any> | Array<Record<string, any>>; // Optional data field
  version?: string; // Version of the response, default to "1.0"
};

export type TRetryOptions = {
  maxRetries: number;
  initialDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
};

export type TMessageHandler = (message: TWsMessage) => void | Promise<void>;
export type TMessageHandlerMap = {
  [key in TWsEventActionValue]?: TMessageHandler[];
};

export type TWebSocketConfig = {
  url: string;
  eventEmitter: EventEmitter;
  protocols?: string[];
  retryOptions?: TRetryOptions;
  pingInterval?: number;
  pongTimeout?: number;
  messageTimeout?: number;
};
