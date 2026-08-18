import { makeAutoObservable, runInAction } from "mobx";

import {
  ContactDraftStorage,
  type ContactDraftContext,
  type StoredContactDraft,
} from "@/features/contacts/contact-draft-storage";
import {
  ContactsService,
  ContactsServiceError,
} from "@/features/contacts/contacts.service";
import type {
  Contact,
  ContactFormValues,
} from "@/features/contacts/contacts.types";

type ContactFormField = keyof ContactFormValues;

const DRAFT_ERROR =
  "This browser could not save the local draft. Keep this tab open until the contact is saved.";

class ContactFormStore {
  draftStorageErrorMessage: string | null = null;
  errorMessage: string | null = null;
  fieldErrors: Partial<Record<ContactFormField, string>> = {};
  hasLocalDraft = false;
  isLoading = false;
  isSubmitting = false;
  savedAt: string | null = null;
  serverContact: Contact | null = null;
  values: ContactFormValues = emptyValues();

  private baselineValues: ContactFormValues = emptyValues();
  private context: ContactDraftContext | null = null;
  private contextKey: string | null = null;
  private readonly service: ContactsService;
  private readonly storage: ContactDraftStorage;

  constructor(service: ContactsService, storage: ContactDraftStorage) {
    this.service = service;
    this.storage = storage;
    makeAutoObservable<
      this,
      "baselineValues" | "context" | "contextKey" | "service" | "storage"
    >(
      this,
      {
        baselineValues: false,
        context: false,
        contextKey: false,
        service: false,
        storage: false,
      },
      { autoBind: true },
    );
  }

  get isDirty(): boolean {
    return JSON.stringify(this.values) !== JSON.stringify(this.baselineValues);
  }

  isActiveFor(context: ContactDraftContext): boolean {
    return this.contextKey === buildContextKey(context);
  }

  beginCreate(context: Omit<ContactDraftContext, "contactId" | "mode">): void {
    const next = { ...context, contactId: null, mode: "create" as const };
    if (this.contextKey === buildContextKey(next)) return;
    this.reset(next);
    const draft = this.storage.read(next);
    if (draft !== null) this.applyDraft(draft);
  }

  startNew(context: Omit<ContactDraftContext, "contactId" | "mode">): void {
    const next = { ...context, contactId: null, mode: "create" as const };
    this.storage.clear(next);
    this.reset(next);
  }

  async beginEdit(
    context: Omit<ContactDraftContext, "mode"> & { contactId: string },
  ): Promise<void> {
    const next = { ...context, mode: "edit" as const };
    const key = buildContextKey(next);
    if (this.contextKey === key) return;
    this.reset(next);
    this.isLoading = true;
    try {
      const contact = await this.service.getContact(
        next.organizationId,
        next.contactId,
      );
      if (this.contextKey !== key) return;
      runInAction(() => {
        this.serverContact = contact;
        this.baselineValues = valuesFromContact(contact);
        this.values = cloneValues(this.baselineValues);
        const draft = this.storage.read(next);
        if (draft !== null) this.applyDraft(draft);
      });
    } catch {
      if (this.contextKey === key) {
        runInAction(() => {
          this.errorMessage =
            "This contact could not be loaded. It may no longer exist.";
        });
      }
    } finally {
      if (this.contextKey === key) {
        runInAction(() => {
          this.isLoading = false;
        });
      }
    }
  }

  setField<Field extends ContactFormField>(
    field: Field,
    value: ContactFormValues[Field],
  ): void {
    this.values = { ...this.values, [field]: value };
    const errors = { ...this.fieldErrors };
    delete errors[field];
    this.fieldErrors = errors;
    this.errorMessage = null;
    this.persistDraft();
  }

  discardLocalDraft(): void {
    if (this.context === null) return;
    this.storage.clear(this.context);
    this.values = cloneValues(this.baselineValues);
    this.fieldErrors = {};
    this.errorMessage = null;
    this.draftStorageErrorMessage = null;
    this.hasLocalDraft = false;
    this.savedAt = null;
  }

  async submit(): Promise<Contact | null> {
    if (this.context === null || this.isSubmitting) return null;
    const fieldErrors = validateValues(this.values);
    if (Object.keys(fieldErrors).length > 0) {
      this.fieldErrors = fieldErrors;
      this.errorMessage =
        "Review the highlighted contact details before saving.";
      return null;
    }

    const context = this.context;
    const key = this.contextKey;
    this.isSubmitting = true;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.persistDraft();
    try {
      const contact =
        context.mode === "create"
          ? await this.service.createContact(
              context.organizationId,
              toInput(this.values),
            )
          : await this.service.updateContact(
              context.organizationId,
              context.contactId ?? "",
              toInput(this.values),
            );
      if (this.contextKey !== key) return null;
      runInAction(() => {
        this.storage.clear(context);
        if (context.mode === "create") {
          this.reset(context);
        } else {
          this.serverContact = contact;
          this.values = valuesFromContact(contact);
          this.baselineValues = cloneValues(this.values);
          this.hasLocalDraft = false;
          this.savedAt = null;
          this.draftStorageErrorMessage = null;
        }
      });
      return contact;
    } catch (error) {
      if (this.contextKey === key) {
        runInAction(() => {
          this.errorMessage =
            error instanceof ContactsServiceError
              ? error.message
              : "The contact could not be saved. Try again.";
        });
      }
      return null;
    } finally {
      if (this.contextKey === key) {
        runInAction(() => {
          this.isSubmitting = false;
        });
      }
    }
  }

  private applyDraft(draft: StoredContactDraft): void {
    this.values = cloneValues(draft.values);
    this.hasLocalDraft = true;
    this.savedAt = draft.savedAt;
  }

  private persistDraft(): void {
    if (this.context === null) return;
    if (!this.isDirty) {
      this.storage.clear(this.context);
      this.hasLocalDraft = false;
      this.savedAt = null;
      this.draftStorageErrorMessage = null;
      return;
    }
    const savedAt = new Date().toISOString();
    const saved = this.storage.write(this.context, {
      savedAt,
      values: cloneValues(this.values),
      version: 1,
    });
    this.hasLocalDraft = saved;
    this.savedAt = saved ? savedAt : this.savedAt;
    this.draftStorageErrorMessage = saved ? null : DRAFT_ERROR;
  }

  private reset(context: ContactDraftContext): void {
    this.context = context;
    this.contextKey = buildContextKey(context);
    this.baselineValues = emptyValues();
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.hasLocalDraft = false;
    this.isLoading = false;
    this.isSubmitting = false;
    this.savedAt = null;
    this.serverContact = null;
    this.values = emptyValues();
  }
}

function emptyValues(): ContactFormValues {
  return {
    externalId: "",
    name: "",
    preferences: {},
    primaryEmail: "",
    primaryPhone: "",
  };
}

function cloneValues(values: ContactFormValues): ContactFormValues {
  return { ...values, preferences: { ...values.preferences } };
}

function valuesFromContact(contact: Contact): ContactFormValues {
  return {
    externalId: contact.externalId ?? "",
    name: contact.name ?? "",
    preferences: { ...(contact.preferences ?? {}) },
    primaryEmail: contact.primaryEmail ?? "",
    primaryPhone: contact.primaryPhone ?? "",
  };
}

function toInput(values: ContactFormValues) {
  return {
    externalId: nullable(values.externalId),
    name: nullable(values.name),
    preferences: { ...values.preferences },
    primaryEmail: nullable(values.primaryEmail),
    primaryPhone: nullable(values.primaryPhone),
  };
}

function nullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function validateValues(
  values: ContactFormValues,
): Partial<Record<ContactFormField, string>> {
  const errors: Partial<Record<ContactFormField, string>> = {};
  if (values.name.length > 255) errors.name = "Use 255 characters or fewer.";
  const email = values.primaryEmail.trim();
  if (email !== "" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.primaryEmail = "Enter a valid email address.";
  }
  const phone = values.primaryPhone.trim();
  if (phone !== "" && !/^\+[1-9]\d{1,14}$/.test(phone)) {
    errors.primaryPhone = "Use E.164 format, for example +14155552671.";
  }
  return errors;
}

function buildContextKey(context: ContactDraftContext): string {
  return [
    context.memberKey,
    context.organizationId,
    context.mode,
    context.contactId,
  ].join(":");
}

export { ContactFormStore };
