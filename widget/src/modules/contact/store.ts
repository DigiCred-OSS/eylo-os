import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { RepositoryMixin } from "@eylo/base/RepositoryMixin";
import type { EyloStore } from "@eylo/store";

import type { Contact } from "./model";

export type ContactStoreState = {
  contacts: Array<Contact>;
};

// Apply the mixin
const ContactStoreBase = RepositoryMixin<Contact, ContactStoreState, "contacts">("contacts")(
  BaseReactiveStore<ContactStoreState>
);

class ContactStore extends ContactStoreBase {
  // TODO: implement singleton pattern for all stores
  private static _instance: ContactStore | null = null;
  // @ts-ignore
  private _parent: EyloStore;
  constructor(parent: EyloStore) {
    if (ContactStore._instance) {
      return ContactStore._instance;
    }
    const initialState: ContactStoreState = {
      contacts: [],
    };
    super(initialState, "eylo:contact:");
    this._parent = parent;
    ContactStore._instance = this;
  }
}

export { ContactStore };
