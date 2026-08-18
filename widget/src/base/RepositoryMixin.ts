import type { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { logger } from "@eylo/utils";

// RepositoryMixin.ts
export type Constructor<T = {}> = new (...args: any[]) => T;

type TEntityWithPKExtId = {
  id: string;
  externalId?: string;
};

export type RepositoryMethods<T extends TEntityWithPKExtId> = {
  add_(item: T): void;
  get_(id: string): T | undefined;
  get_byExternalId(externalId: string): T | undefined;
  delete_(id: string): void;
  list_(): Array<T>;
  update_(item: T): void;
  clear_(): void;
};

function RepositoryMixin<
  T extends TEntityWithPKExtId,
  S extends Record<string, any>,
  K extends keyof S,
>(itemsKey: K) {
  return function <TBase extends Constructor<BaseReactiveStore<S>>>(
    Base: TBase
  ): TBase & Constructor<RepositoryMethods<T>> {
    return class extends Base {
      add_(item: T): void {
        const items = this.get(itemsKey) as Array<T>;
        if (!this.get_(item.id)) {
          this.set(itemsKey, [...items, item] as S[K]);
        }
      }

      get_(id: string): T | undefined {
        const items = this.get(itemsKey) as Array<T>;
        return items.find((item) => item.id === id) || undefined;
      }

      get_byExternalId(externalId: string): T | undefined {
        const items = this.get(itemsKey) as Array<T>;
        return items.find((item) => item.externalId === externalId) || undefined;
      }

      delete_(id: string): void {
        const items = this.get(itemsKey) as Array<T>;
        this.set(itemsKey, items.filter((item) => item.id !== id) as S[K]);
      }

      list_(): Array<T> {
        return this.get(itemsKey) as Array<T>;
      }

      update_(item: T): void {
        const items = this.get(itemsKey) as Array<T>;
        const index = items.findIndex((c) => c.id === item.id);
        if (index !== -1) {
          const newItems = [...items];
          newItems[index] = item;
          this.set(itemsKey, newItems as S[K]);
        } else {
          logger.warn(`Item with id ${item.id} not found for update.`);
        }
      }

      clear_(): void {
        this.set(itemsKey, [] as S[K]);
      }
    };
  };
}

export { RepositoryMixin };
