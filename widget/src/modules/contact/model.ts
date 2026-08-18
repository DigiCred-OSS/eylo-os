import type { TContact } from "./types";

class Contact {
  private _id: string;
  private _externalId?: string;
  private _name?: string;
  private _primaryEmail?: string;
  private _primaryPhone?: string;
  private _preferences: Record<string, string>;
  constructor(data: TContact) {
    this._id = data.id;
    this._externalId = data.externalId;
    this._name = data.name;
    this._primaryEmail = data.primaryEmail;
    this._primaryPhone = data.primaryPhone;
    this._preferences = data.preferences ?? {};
  }
  get id(): string {
    return this._id;
  }
  get externalId(): string | undefined {
    return this._externalId;
  }
  get name(): string | undefined {
    return this._name;
  }
  get primaryEmail(): string | undefined {
    return this._primaryEmail;
  }
  get primaryPhone(): string | undefined {
    return this._primaryPhone;
  }
  get preferences(): Record<string, string> {
    return this._preferences;
  }
}

export { Contact };
