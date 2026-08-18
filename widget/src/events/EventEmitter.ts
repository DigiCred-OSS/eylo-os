import { logger } from "@eylo/utils";

import type { EventPayloadTuple, EventTypes } from "./EventTypes";

type EventListener<E extends EventTypes> = (...args: EventPayloadTuple<E>) => void | Promise<void>;
type TEventListeners = { [K in EventTypes]?: Array<EventListener<K>> };
export class EventEmitter {
  private listeners: TEventListeners = {};

  on<E extends EventTypes>(event: E, listener: EventListener<E>): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(listener as never);
    logger.debug(`EventEmitter: Registering listener for event: ${event} ${listener.name}`);
  }

  off<E extends EventTypes>(event: E, listener: EventListener<E>): void {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter((l) => l !== listener) as never;
    logger.debug(`EventEmitter: Unregistering listener for event: ${event} ${listener.name}`);
  }

  emit = async <E extends EventTypes>(event: E, ...args: EventPayloadTuple<E>): Promise<void> => {
    if (!this.listeners[event]) return;
    const handlers = this.listeners[event] as Array<EventListener<E>>;
    for (const handler of handlers) {
      logger.debug(`EventEmitter: Emitting event: ${event} ${handler.name}`);
      try {
        const result = handler(...args);
        if (result instanceof Promise) {
          try {
            await result;
          } catch (error) {
            logger.error(`Error in async message handler for ${event}:`, event, error);
          }
        }
      } catch (error) {
        logger.error(`Error in message handler for ${event}:`, event, error);
      }
    }
  };
}
