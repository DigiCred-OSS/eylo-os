import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { RepositoryMixin } from "@eylo/base/RepositoryMixin";
import type { EyloStore } from "@eylo/store";

import type { Conversation } from "./model";
import { MessageStore } from "../message/store";

export type ConversationStoreState = {
  conversations: Array<Conversation>;
};

// Apply the mixin
const ConversationStoreBase = RepositoryMixin<
  Conversation,
  ConversationStoreState,
  "conversations"
>("conversations")(BaseReactiveStore<ConversationStoreState>);

class ConversationStore extends ConversationStoreBase {
  // TODO: implement singleton pattern for all stores
  private static _instance: ConversationStore | null = null;
  // @ts-ignore
  private _parent: EyloStore;
  // @ts-ignore
  private _messageStore: MessageStore;
  constructor(parent: EyloStore) {
    if (ConversationStore._instance) {
      return ConversationStore._instance;
    }
    const initialState: ConversationStoreState = {
      conversations: [],
    };
    super(initialState, "eylo:conversation:");
    this._parent = parent;
    this._messageStore = new MessageStore(this._parent);
    ConversationStore._instance = this;
  }
  get messageStore(): MessageStore {
    return this._messageStore;
  }
  setUnreadCount(conversationId: string, unreadCount: number): void {
    const conversation = this.get_(conversationId);
    if (conversation) {
      this.update_(conversation.withUnreadCount(unreadCount));
    }
  }
  incrementUnread(conversationId: string): void {
    const conversation = this.get_(conversationId);
    if (conversation) {
      this.update_(conversation.withUnreadCount(conversation.unreadCount + 1));
    }
  }
  recordMessageActivity(
    conversationId: string,
    createdAt: Date,
    incrementUnread: boolean
  ): void {
    const conversation = this.get_(conversationId);
    if (conversation) {
      this.update_(conversation.withMessageActivity(createdAt, incrementUnread));
    }
  }
}

export { ConversationStore };
