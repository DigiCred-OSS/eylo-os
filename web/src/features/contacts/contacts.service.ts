import type { ApiClient } from "@/api/client";
import { toContactListApiQuery } from "@/features/contacts/contacts.query";
import type {
  Contact,
  ContactCollectionQuery,
  ContactCreateInput,
  ContactsPage,
  ContactUpdateInput,
  DeletionJob,
} from "@/features/contacts/contacts.types";

class ContactsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ContactsServiceError";
    this.status = status;
  }
}

class ContactsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listContacts(
    organizationId: string,
    query: ContactCollectionQuery,
    signal?: AbortSignal,
  ): Promise<ContactsPage> {
    return requireData(
      await this.api.GET("/api/{organization_id}/contacts", {
        params: {
          path: { organization_id: organizationId },
          query: toContactListApiQuery(query),
        },
        signal,
      }),
      "Contacts could not be loaded.",
    );
  }

  async getContact(
    organizationId: string,
    contactId: string,
    signal?: AbortSignal,
  ): Promise<Contact> {
    return requireData(
      await this.api.GET("/api/{organization_id}/contacts/{contact_id}", {
        params: {
          path: { contact_id: contactId, organization_id: organizationId },
        },
        signal,
      }),
      "This contact could not be loaded.",
    );
  }

  async createContact(
    organizationId: string,
    input: ContactCreateInput,
  ): Promise<Contact> {
    return requireData(
      await this.api.POST("/api/{organization_id}/contacts", {
        body: input,
        params: { path: { organization_id: organizationId } },
      }),
      "The contact could not be created.",
    );
  }

  async updateContact(
    organizationId: string,
    contactId: string,
    input: ContactUpdateInput,
  ): Promise<Contact> {
    return requireData(
      await this.api.PATCH("/api/{organization_id}/contacts/{contact_id}", {
        body: input,
        params: {
          path: { contact_id: contactId, organization_id: organizationId },
        },
      }),
      "The contact could not be updated.",
    );
  }

  async requestDeletion(
    organizationId: string,
    contactId: string,
  ): Promise<DeletionJob> {
    return requireData(
      await this.api.DELETE("/api/{organization_id}/contacts/{contact_id}", {
        params: {
          path: { contact_id: contactId, organization_id: organizationId },
        },
      }),
      "Contact deletion could not be requested.",
    );
  }
}

function requireData<Data>(
  result: { data?: Data; error?: unknown; response: Response },
  fallback: string,
): Data {
  if (result.response.ok && result.data !== undefined) return result.data;
  throw new ContactsServiceError(
    apiErrorMessage(result.error, fallback),
    result.response.status,
  );
}

function apiErrorMessage(error: unknown, fallback: string): string {
  if (!isRecord(error)) return fallback;
  if (typeof error.detail === "string") return error.detail;
  if (Array.isArray(error.detail)) {
    const messages = error.detail
      .map((item) =>
        isRecord(item) && typeof item.msg === "string" ? item.msg : null,
      )
      .filter((message): message is string => message !== null);
    if (messages.length > 0) return messages.join(" ");
  }
  return fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { ContactsService, ContactsServiceError };
