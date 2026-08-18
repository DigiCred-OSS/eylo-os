import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { RepositoryMixin } from "@eylo/base/RepositoryMixin";
import type { EyloStore } from "@eylo/store";

import type { TParticipant } from "./types";

export type ParticipantStoreState = {
  participants: Array<TParticipant>;
};

// Apply the mixin
const ParticipantStoreBase = RepositoryMixin<TParticipant, ParticipantStoreState, "participants">(
  "participants"
)(BaseReactiveStore<ParticipantStoreState>);

class ParticipantStore extends ParticipantStoreBase {
  // TODO: implement singleton pattern for all stores
  private static _instance: ParticipantStore | null = null;
  // @ts-ignore
  private _parent: EyloStore;
  constructor(parent: EyloStore) {
    if (ParticipantStore._instance) {
      return ParticipantStore._instance;
    }
    const initialState: ParticipantStoreState = {
      participants: [],
    };
    super(initialState, "eylo:conversation:");
    this._parent = parent;
    ParticipantStore._instance = this;
  }
}

export { ParticipantStore };
