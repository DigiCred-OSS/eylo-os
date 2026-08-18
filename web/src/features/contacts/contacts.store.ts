import { makeAutoObservable, runInAction } from "mobx";

import { ContactDraftStorage } from "@/features/contacts/contact-draft-storage";
import { ContactFormStore } from "@/features/contacts/contact-form.store";
import {
  ContactsService,
  ContactsServiceError,
} from "@/features/contacts/contacts.service";
import type {
  Contact,
  ContactCollectionQuery,
  DeletionJob,
} from "@/features/contacts/contacts.types";

class ContactsStore {
  collectionErrorMessage: string | null = null;
  deleteErrorMessage: string | null = null;
  deletionJob: DeletionJob | null = null;
  hasMore = false;
  isCollectionLoading = false;
  isDeleting = false;
  isSelectedLoading = false;
  items: Contact[] = [];
  limit = 20;
  page = 1;
  selectedContact: Contact | null = null;
  selectedErrorMessage: string | null = null;
  total = 0;

  readonly form: ContactFormStore;
  private collectionRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: ContactsService;

  constructor(service: ContactsService, draftStorage: ContactDraftStorage) {
    this.service = service;
    this.form = new ContactFormStore(service, draftStorage);
    makeAutoObservable<
      this,
      "collectionRequest" | "selectedRequest" | "service"
    >(
      this,
      {
        collectionRequest: false,
        form: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(
    organizationId: string,
    query: ContactCollectionQuery,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    try {
      const page = await this.service.listContacts(
        organizationId,
        query,
        request.signal,
      );
      if (request.signal.aborted) return;
      runInAction(() => {
        this.hasMore = page.hasMore === true;
        this.items = page.data;
        this.limit = page.limit;
        this.page = page.page;
        this.total = page.total ?? page.data.length;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.collectionErrorMessage =
            "Contacts could not be loaded. Check the API connection and try again.";
        });
      }
    } finally {
      if (this.collectionRequest === request) {
        runInAction(() => {
          this.collectionRequest = null;
          this.isCollectionLoading = false;
        });
      }
    }
  }

  async loadSelected(organizationId: string, contactId: string): Promise<void> {
    this.selectedRequest?.abort();
    const request = new AbortController();
    this.selectedRequest = request;
    this.selectedContact =
      this.items.find((contact) => contact.id === contactId) ?? null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;
    try {
      const contact = await this.service.getContact(
        organizationId,
        contactId,
        request.signal,
      );
      if (request.signal.aborted) return;
      runInAction(() => {
        this.selectedContact = contact;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.selectedContact = null;
          this.selectedErrorMessage =
            "This contact could not be loaded. It may no longer exist.";
        });
      }
    } finally {
      if (this.selectedRequest === request) {
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
      }
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedContact = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
  }

  clearDeleteState(): void {
    this.deleteErrorMessage = null;
    this.deletionJob = null;
  }

  async requestDeletion(
    organizationId: string,
    contactId: string,
  ): Promise<boolean> {
    if (this.isDeleting) return false;
    this.isDeleting = true;
    this.deleteErrorMessage = null;
    this.deletionJob = null;
    try {
      const job = await this.service.requestDeletion(organizationId, contactId);
      runInAction(() => {
        this.deletionJob = job;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.deleteErrorMessage =
          error instanceof ContactsServiceError
            ? error.message
            : "Contact deletion could not be requested. Try again.";
      });
      return false;
    } finally {
      runInAction(() => {
        this.isDeleting = false;
      });
    }
  }
}

export { ContactsStore };
