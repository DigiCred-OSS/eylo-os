import type { TConversation, TConversationChannel, TConversationStatus } from "./types";

class Conversation {
  private _id: string;
  private _status: TConversationStatus;
  private _channel: TConversationChannel;
  private _endedAt?: Date | null;
  private _meta?: Record<string, any> | null;
  private _createdAt: Date;
  private _updatedAt: Date;
  private _externalId: string;
  private _organizationId: string;
  private _title: string;
  private _messageCount?: number;
  private _unreadCount: number;
  constructor(data: TConversation) {
    this._id = data.id;
    this._status = data.status;
    this._channel = data.channel;
    this._endedAt = data.endedAt ?? null;
    this._meta = data.meta ?? null;
    this._createdAt = new Date(data.createdAt);
    this._updatedAt = new Date(data.updatedAt);
    this._externalId = data.externalId;
    this._organizationId = data.organizationId;
    this._title = data.title;
    this._messageCount = data.messageCount;
    this._unreadCount = Math.max(0, data.unreadCount ?? 0);
  }
  get id(): string {
    return this._id;
  }
  get status(): TConversationStatus {
    return this._status;
  }
  get channel(): TConversationChannel {
    return this._channel;
  }
  get endedAt(): Date | null {
    return this._endedAt ? new Date(this._endedAt) : null;
  }
  get meta(): Record<string, any> | null {
    return this._meta ? { ...this._meta } : null;
  }
  get createdAt(): Date {
    return new Date(this._createdAt);
  }
  get updatedAt(): Date {
    return new Date(this._updatedAt);
  }
  get externalId(): string {
    return this._externalId;
  }
  get organizationId(): string {
    return this._organizationId;
  }
  get title(): string {
    return this._title;
  }
  get messageCount(): number | undefined {
    return this._messageCount;
  }
  get unreadCount(): number {
    return this._unreadCount;
  }
  withUnreadCount(unreadCount: number): Conversation {
    return this.copy({ unreadCount });
  }
  withMessageActivity(createdAt: Date, incrementUnread: boolean): Conversation {
    const updatedAt = createdAt > this._updatedAt ? createdAt : this._updatedAt;
    const unreadCount = incrementUnread ? this.unreadCount + 1 : this.unreadCount;
    return this.copy({ updatedAt, unreadCount });
  }
  private copy(
    changes: { updatedAt?: Date; unreadCount?: number } = {}
  ): Conversation {
    return new Conversation({
      id: this.id,
      status: this.status,
      channel: this.channel,
      endedAt: this.endedAt,
      meta: this.meta,
      createdAt: this.createdAt,
      updatedAt: changes.updatedAt ?? this.updatedAt,
      externalId: this.externalId,
      organizationId: this.organizationId,
      title: this.title,
      messageCount: this.messageCount,
      unreadCount: changes.unreadCount ?? this.unreadCount,
    });
  }
}

export { Conversation };
