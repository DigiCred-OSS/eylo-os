import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { RepositoryMixin } from "@eylo/base/RepositoryMixin";
import type { EyloStore } from "@eylo/store";

import type { Agent } from "./model";

export type AgentStoreState = {
  agents: Array<Agent>;
};

// Apply the mixin
const AgentStoreBase = RepositoryMixin<Agent, AgentStoreState, "agents">("agents")(
  BaseReactiveStore<AgentStoreState>
);

class AgentStore extends AgentStoreBase {
  // TODO: implement singleton pattern for all stores
  private static _instance: AgentStore | null = null;
  // @ts-ignore
  private _parent: EyloStore;
  constructor(parent: EyloStore) {
    if (AgentStore._instance) {
      return AgentStore._instance;
    }
    const initialState: AgentStoreState = {
      agents: [],
    };
    super(initialState, "eylo:agent:");
    this._parent = parent;
    AgentStore._instance = this;
  }
}

export { AgentStore };
