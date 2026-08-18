import { EYLO_EVENTS } from "@eylo/events";
import type { TWsMessage } from "@eylo/net";
import { WS_ACTIONS } from "@eylo/net/constants";
import type { EyloStore } from "@eylo/store";
import { logger } from "@eylo/utils";

import { Contact } from "./model";
import type { ContactStore } from "./store";
import type { TContact, TContactCreate } from "./types";

// refactor this to just depend on ContactStore
class ContactService {
  private static _instance: ContactService | undefined = undefined;
  // @ts-ignore
  private _eyloStore: EyloStore;
  // @ts-ignore
  private _contactStore: ContactStore;
  constructor(eyloStore: EyloStore) {
    if (ContactService._instance) {
      return ContactService._instance;
    }
    this._eyloStore = eyloStore;
    this._contactStore = this._eyloStore.contactStore;
    this._installHandlers();
    ContactService._instance = this;
  }

  private _model_to_type = (contact: Contact): TContact => {
    return {
      id: contact.id,
      externalId: contact.externalId,
      name: contact.name,
      primaryEmail: contact.primaryEmail,
      primaryPhone: contact.primaryPhone,
      preferences: contact.preferences,
    } as TContact;
  };

  private _identifiedHandler = () => {
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.CONTACT_IDENTIFIED, (message) => {
      if (message.data) {
        const contact = new Contact(message.data);
        this._contactStore.add_(contact);
        this._eyloStore.ee.emit(EYLO_EVENTS.CONTACT_IDENTIFIED, contact);
      } else {
        logger.warn("Received contact identified message without data.");
      }
    });
  };

  private _updatedHandler = () => {
    const _handler = (message: TWsMessage) => {
      if (message.data) {
        const contact = new Contact(message.data);
        this._contactStore.update_(contact);
        this._eyloStore.ee.emit(EYLO_EVENTS.CONTACT_UPDATED, contact);
      } else {
        logger.warn("Received contact updated message without data.");
      }
    };
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.CONTACT_UPDATED, _handler);
  };

  private _contactQueryHandler = () => {
    const _handler = (message: TWsMessage) => {
      if (message.data) {
        message.data.forEach((m: TContact) => {
          const contact = new Contact(m);
          this._contactStore.add_(contact);
          this._eyloStore.ee.emit(EYLO_EVENTS.CONTACT_CREATED, contact);
        });
      } else {
        logger.warn("Received contact query message without data.");
      }
    };
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.CONTACT_QUERY, _handler);
  };

  private _installHandlers = (): void => {
    this._identifiedHandler();
    this._updatedHandler();
    this._contactQueryHandler();
  };

  public identify = (data: TContactCreate): void => {
    const contact = {
      id: data.id,
      organizationId: this._eyloStore.store.organizationId,
      externalId: data.externalId,
      name: data.name,
      primaryEmail: data.primaryEmail,
      primaryPhone: data.primaryPhone,
      preferences: data.preferences ?? {},
    };

    this._eyloStore.cm.send({
      kind: WS_ACTIONS.CONTACT_IDENTIFIED,
      data: contact,
    } as TWsMessage);
  };

  public resolveContact_byID(contactId: string): TContact | undefined {
    const contact = this._contactStore.get_(contactId);
    if (!contact) {
      this._eyloStore.cm.send({
        kind: WS_ACTIONS.CONTACT_QUERY,
        data: {
          filters: {
            contactIds: [contactId],
          },
        },
        requestId: contactId,
      } as TWsMessage);
      logger.warn(`Contact with ID ${contactId} not found.`);
      return;
    }
    return this._model_to_type(contact);
  }

  public resolveContact_byExternalID(externalId: string): TContact | undefined {
    const contact = this._contactStore.get_byExternalId(externalId);
    if (!contact) {
      this._eyloStore.cm.send({
        kind: WS_ACTIONS.CONTACT_QUERY,
        data: {
          filters: {
            externalIds: [externalId],
          },
        },
        requestId: externalId,
      } as TWsMessage);
      logger.warn(`Contact with external ID ${externalId} not found.`);
      return;
    }
    return this._model_to_type(contact);
  }
}

export { ContactService };
