// Type definitions for event details
import { logger } from "@eylo/utils";
import { isEqual } from "es-toolkit";

type StateChangeDetail<T> = {
  prev: T;
  value: T;
};

type PropertyChangeDetail<K, V> = {
  key: K;
  prev: V;
  value: V | undefined | null;
};

const STATE_CHANGE_EVENT = "stateChange";
const MAX_RECURSION_DEPTH = 100;

class BaseReactiveStore<T extends Record<string, any>> extends EventTarget {
  private _destroyed: boolean = false;
  private _state: T = {} as T;
  private _computedCache: Map<keyof T, any> = new Map();
  private _computedDependencies: Map<keyof T, Set<keyof T>> = new Map();
  private _pendingUpdates: Map<keyof T, PropertyChangeDetail<keyof T, T[keyof T]>> = new Map();
  private _flushScheduled: boolean = false;
  private _computedProperties: Set<keyof T> = new Set();
  private _namespace: string = "eylo:";
  constructor(initialState: T, namespace?: string) {
    super();
    if (namespace) {
      this._namespace = namespace;
    }
    this.initializeState(initialState);
  }

  private hydrateEventName = (name: string): string => {
    return `${this._namespace}${name}`;
  };

  get state(): T {
    return this._state;
  }

  private initializeState(initialState: T): void {
    this._state = { ...initialState };
    this._destroyed = false;

    // Create reactive getters/setters for initial state
    for (const key in initialState) {
      this.defineReactiveProperty(key);
    }
  }

  // Define reactive property with getter/setter
  private defineReactiveProperty(key: keyof T): void {
    // Don't overwrite computed properties
    if (this._computedProperties.has(key)) {
      logger.warn(
        `Cannot define reactive property "${String(key)}" - it's already a computed property`
      );
      return;
    }

    // Check if property already has a descriptor (avoid conflicts)
    const existingDescriptor = Object.getOwnPropertyDescriptor(this, key);
    if (existingDescriptor) {
      logger.warn(
        `Property "${String(key)}" already has a descriptor, skipping reactive definition`
      );
      return;
    }

    Object.defineProperty(this, key, {
      get: () => this._state[key],
      set: (value) => this._set(key, value),
      enumerable: true,
      configurable: true,
    });
  }

  // Core state setter with change detection
  private _set<F extends keyof T>(key: F, value: T[F]): void {
    if (this._destroyed) {
      logger.warn(
        `Attempted to set property "${String(key)}" on a destroyed store. Ignoring update.`
      );
      return;
    }

    // Prevent setting computed properties
    if (this._computedProperties.has(key)) {
      logger.warn(
        `Cannot set computed property "${String(key)}". Computed properties are read-only.`
      );
      return;
    }

    // dynamically define the property if it doesn't exist
    if (!this._has(key)) {
      this.defineReactiveProperty(key);
    }
    const prev = this._state[key];
    if (isEqual(prev, value)) return; // No change, skip update
    this._state[key] = value;
    this._pendingUpdates.set(key, {
      key,
      prev,
      value,
    } as PropertyChangeDetail<F, T[F]>);
    this._invalidateDependent(key);
    this._scheduleFlush();
  }

  private _get<F extends keyof T>(key: F): T[F] {
    if (this._computedDependencies.has(key)) {
      // typesafe-ignore-next-line
      //   const descriptor = Object.getOwnPropertyDescriptor(this, key);
      //   if (descriptor?.get) {
      //     return descriptor.get.call(this);
      //   }
      return (this as any)[key]; // Use getter
    }
    return this._state[key];
  }

  private _has<F extends keyof T>(key: F): boolean {
    return key in this._state || this._computedProperties.has(key);
  }

  private _delete<F extends keyof T>(key: F): void {
    if (this._has(key)) {
      const prev = this._state[key];
      delete this._state[key];
      this._pendingUpdates.set(key, {
        key,
        prev,
        value: undefined,
      } as PropertyChangeDetail<F, T[F]>);
      this._scheduleFlush();
    }
  }

  // COMPUTE SUPPORT //
  private _computed<F extends keyof T>(key: F, fn: () => T[F], dependencies: (keyof T)[]): void {
    // Check if this property already exists as a reactive property
    if (key in this._state && !this._computedProperties.has(key)) {
      logger.warn(
        `Property "${String(
          key
        )}" already exists as a reactive property. Cannot convert to computed.`
      );
      return;
    }

    // Check if it's already a computed property
    if (this._computedProperties.has(key)) {
      logger.warn(`Property "${String(key)}" is already defined as a computed property.`);
      return;
    }

    // Mark as computed property
    this._computedProperties.add(key);
    this._computedDependencies.set(key, new Set(dependencies));

    Object.defineProperty(this, key, {
      get: () => {
        if (!this._computedCache.has(key)) {
          const value = fn();
          this._computedCache.set(key, value);
        }
        return this._computedCache.get(key);
      },
      enumerable: true,
      configurable: true,
    });
    (this as any)[key]; // Trigger getter to compute initial value
  }

  // Invalidate computed values that depend on this key
  private _invalidateDependent<F extends keyof T>(key: F, depth: number = 0): void {
    if (depth > MAX_RECURSION_DEPTH) {
      logger.warn(`Maximum depth reached while invalidating dependencies for key: ${String(key)}`);
      return;
    }
    const invalidated = new Set<keyof T>();
    for (const [computedKey, dependencies] of this._computedDependencies.entries()) {
      if (dependencies.has(key)) {
        const oldValue = this._computedCache.get(computedKey);
        this._computedCache.delete(computedKey);
        invalidated.add(computedKey);
        const newValue = (this as any)[computedKey]; // Trigger getter to recompute
        if (isEqual(oldValue, newValue)) {
          continue;
        }
        this._pendingUpdates.set(computedKey, {
          key: computedKey,
          prev: oldValue,
          value: newValue,
        } as PropertyChangeDetail<F, T[F]>);
      }
    }
    for (const invalidatedKey of invalidated) {
      this._invalidateDependent(invalidatedKey, depth + 1);
    }
    this._scheduleFlush();
  }

  //   BATCH SUPPORT //
  private _scheduleFlush = (): void => {
    if (this._destroyed) {
      logger.warn("Store is destroyed, ignoring flush request.");
      return;
    }
    if (this._flushScheduled) return;
    this._flushScheduled = true;
    // Use requestAnimationFrame to batch updates
    requestAnimationFrame(() => this._flushChanges());
  };

  private _flushChanges = (): void => {
    this._flushScheduled = false;
    if (this._pendingUpdates.size === 0) return;
    const updates = Array.from(this._pendingUpdates.entries());
    for (const [key, detail] of updates) {
      this._emit(key as string, detail);
    }
    this._pendingUpdates.clear();
  };

  // Broadcast updates to all subscribers
  private _emit(
    name: string,
    detail?: StateChangeDetail<T> | PropertyChangeDetail<keyof T, T[keyof T]>
  ): void {
    this.dispatchEvent(new CustomEvent(this.hydrateEventName(name), { detail }));
  }

  // PUBLIC APIs

  public getSnapshot(): T {
    return { ...this._state };
  }

  public reset(newState: T): void {
    const oldState = { ...this._state };

    // Set new properties
    for (const key in newState) {
      this._set(key, newState[key]);
    }

    // Delete properties that no longer exist
    for (const key in oldState) {
      if (!(key in newState)) {
        this._delete(key as keyof T);
      }
    }
  }

  public destroy(): void {
    this._destroyed = true;
    this._computedCache.clear();
    this._computedDependencies.clear();
    this._computedProperties.clear();
    this._pendingUpdates.clear();
    this._flushScheduled = false;
  }

  public set<K extends keyof T>(key: K, value: T[K]): void {
    this._set(key, value);
  }

  public get<K extends keyof T>(key: K): T[K] {
    return this._get(key);
  }

  public computed<K extends keyof T>(key: K, fn: () => T[K], dependencies: (keyof T)[]): void {
    this._computed(key, fn, dependencies);
  }

  public flush(): void {
    if (this._flushScheduled) {
      this._flushScheduled = false; // Reset flag
      this._flushChanges();
    }
  }

  subscribe<F extends keyof T>(
    key: F,
    callback: (detail: PropertyChangeDetail<F, T[F]>) => void
  ): () => void {
    const eventName = this.hydrateEventName(key as string);
    const handler = (event: CustomEvent<PropertyChangeDetail<F, T[F]>>) => {
      callback(event.detail);
    };

    this.addEventListener(eventName, handler as EventListener);

    // Return an unsubscribe function
    return () => {
      this.removeEventListener(eventName, handler as EventListener);
    };
  }

  public subscribeToStateChange<S = T>(
    callback: (detail: StateChangeDetail<S>) => void
  ): () => void {
    const eventName = this.hydrateEventName(STATE_CHANGE_EVENT);
    const handler = (event: CustomEvent<StateChangeDetail<S>>) => {
      callback(event.detail);
    };

    this.addEventListener(eventName, handler as EventListener);

    return () => {
      this.removeEventListener(eventName, handler as EventListener);
    };
  }
}

export { BaseReactiveStore };
