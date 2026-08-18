import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { RepositoryMixin } from "@eylo/base/RepositoryMixin";
import type { EyloStore } from "@eylo/store";

import type { Message } from "./model";

export type MessageStoreState = {
  messages: Array<Message>;
};

// Apply the mixin
const MessageStoreBase = RepositoryMixin<Message, MessageStoreState, "messages">("messages")(
  BaseReactiveStore<MessageStoreState>
);

class MessageStore extends MessageStoreBase {
  private static _instance: MessageStore | null = null;

  // @ts-ignore
  private _parent: EyloStore;
  constructor(parent: EyloStore) {
    if (MessageStore._instance) {
      return MessageStore._instance;
    }
    const initialState: MessageStoreState = {
      messages: [],
    };
    super(initialState, "eylo:conversation:");
    this._parent = parent;
    MessageStore._instance = this;
  }
}

export { MessageStore };
