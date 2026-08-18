import type { TParticipant, TParticipantKind } from "./types";

class Participant {
  private _id: string;
  private _entityKind: TParticipantKind;
  private _entityId: string;
  private _hasInitiated: boolean;
  private _addedByKind?: TParticipantKind | null;
  private _addedById?: string | null;
  private _joinedAt: Date;
  private _isActive: boolean;
  private _removedByKind?: TParticipantKind | null;
  private _removedById?: string | null;
  private _leftAt?: Date | null;
  private _conversationId: string;
  constructor(data: TParticipant) {
    this._id = data.id;
    this._entityKind = data.entityKind;
    this._entityId = data.entityId;
    this._hasInitiated = data.hasInitiated;
    this._addedByKind = data.addedByKind ?? null;
    this._addedById = data.addedById ?? null;
    this._joinedAt = new Date(data.joinedAt);
    this._isActive = data.isActive;
    this._removedByKind = data.removedByKind ?? null;
    this._removedById = data.removedById ?? null;
    this._leftAt = data.leftAt ? new Date(data.leftAt) : null;
    this._conversationId = data.conversationId;
  }
  get id(): string {
    return this._id;
  }
  get entityKind(): TParticipantKind {
    return this._entityKind;
  }
  get entityId(): string {
    return this._entityId;
  }
  get hasInitiated(): boolean {
    return this._hasInitiated;
  }
  get addedByKind(): TParticipantKind | null {
    return this._addedByKind ? this._addedByKind : null;
  }
  get addedById(): string | null {
    return this._addedById ? this._addedById : null;
  }
  get joinedAt(): Date {
    return new Date(this._joinedAt);
  }
  get isActive(): boolean {
    return this._isActive;
  }
  get removedByKind(): TParticipantKind | null {
    return this._removedByKind ? this._removedByKind : null;
  }
  get removedById(): string | null {
    return this._removedById ? this._removedById : null;
  }
  get leftAt(): Date | null {
    return this._leftAt ? new Date(this._leftAt) : null;
  }
  get conversationId(): string {
    return this._conversationId;
  }
}

export { Participant };
