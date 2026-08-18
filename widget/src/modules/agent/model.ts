import type { TAgent, TAgentStatus } from "./types";

class Agent {
  _id: string;
  _name: string;
  _status: TAgentStatus;
  _externalId?: string;
  _description?: string;
  constructor(data: TAgent) {
    this._id = data.id;
    this._name = data.name;
    this._status = data.status;
    this._externalId = data.externalId;
    this._description = data.description;
  }
  get id(): string {
    return this._id;
  }
  get name(): string {
    return this._name;
  }
  get status(): TAgentStatus {
    return this._status;
  }
  get externalId(): string | undefined {
    return this._externalId;
  }
  get description(): string | undefined {
    return this._description;
  }
}

export { Agent };
