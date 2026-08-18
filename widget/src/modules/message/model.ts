import type { TMessage, TMessageContent, TMessageContentKind, TMessageKind } from "./types";

class Message {
  private _id: string;
  private _conversationId: string;
  private _senderParticipantId: string;
  private _kind: TMessageKind;
  private _contentKind: TMessageContentKind;
  private _content: TMessageContent | Record<string, any>;
  private _htmlContent?: string;
  private _parentMessageId?: string;
  private _meta?: Record<string, any>;
  private _externalId?: string;
  private _requestId?: string;
  private _requestFeedback?: string;
  private _createdAt: Date = new Date();

  constructor(data: TMessage) {
    this._id = data.id;
    this._conversationId = data.conversationId;
    this._senderParticipantId = data.senderParticipantId;
    this._kind = data.kind;
    this._contentKind = data.contentKind;
    this._content = data.content;
    this._htmlContent = data.htmlContent;
    this._parentMessageId = data.parentMessageId;
    this._meta = data.meta;
    this._externalId = data.externalId;
    this._requestId = data.requestId;
    this._requestFeedback = data.requestFeedback;
    this._createdAt = new Date(data.createdAt);
  }
  get id(): string {
    return this._id;
  }
  get conversationId(): string {
    return this._conversationId;
  }
  get senderParticipantId(): string {
    return this._senderParticipantId;
  }
  get kind(): TMessageKind {
    return this._kind;
  }
  get contentKind(): TMessageContentKind {
    return this._contentKind;
  }
  get content(): TMessageContent | Record<string, any> {
    return this._content;
  }
  get htmlContent(): string | undefined {
    return this._htmlContent;
  }
  get parentMessageId(): string | undefined {
    return this._parentMessageId;
  }
  get meta(): Record<string, any> | undefined {
    return this._meta;
  }
  get externalId(): string | undefined {
    return this._externalId;
  }
  get requestId(): string | undefined {
    return this._requestId;
  }
  get requestFeedback(): string | undefined {
    return this._requestFeedback;
  }
  get createdAt(): Date {
    return this._createdAt;
  }
}

export { Message };
