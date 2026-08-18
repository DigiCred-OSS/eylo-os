import { Plus, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { useRootStore } from "@/app/use-root-store";
import {
  AppliedFilterBar,
  CollectionToolbar,
  FilterControl,
  SortControl,
} from "@/components/filters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ContactDeleteDialog } from "@/features/contacts/ContactDeleteDialog";
import { ContactDetailsDrawer } from "@/features/contacts/ContactDetailsDrawer";
import { ContactsTable } from "@/features/contacts/ContactsTable";
import {
  CONTACT_FILTER_SCHEMA,
  CONTACT_SORT_OPTIONS,
} from "@/features/contacts/contact-list-controls";
import {
  buildContactCollectionSearchParams,
  DEFAULT_CONTACT_QUERY,
  parseContactCollectionQuery,
} from "@/features/contacts/contacts.query";
import type {
  Contact,
  ContactCollectionQuery,
} from "@/features/contacts/contacts.types";

const ContactsPage = observer(function ContactsPage() {
  const { contacts } = useRootStore();
  const { contactId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [contactToDelete, setContactToDelete] = useState<Contact | null>(null);
  const key = searchParams.toString();
  const query = useMemo(
    () => parseContactCollectionQuery(new URLSearchParams(key)),
    [key],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined)
      void contacts.loadCollection(organizationId, query);
  }, [contacts, organizationId, query]);
  useEffect(() => {
    if (organizationId !== undefined && contactId !== undefined)
      void contacts.loadSelected(organizationId, contactId);
    else contacts.clearSelected();
    return contacts.clearSelected;
  }, [contactId, contacts, organizationId]);
  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;
  const basePath = `/org/${activeOrganizationId}/contacts`;
  const setQuery = (next: ContactCollectionQuery) =>
    setSearchParams(buildContactCollectionSearchParams(next));
  const updateQuery = (patch: Partial<ContactCollectionQuery>) =>
    setQuery({ ...query, ...patch });
  const open = (id: string) =>
    void navigate({ pathname: `${basePath}/${id}`, search: location.search });
  const edit = (id: string) =>
    void navigate({
      pathname: `${basePath}/${id}/edit`,
      search: location.search,
    });
  async function confirmDelete(): Promise<boolean> {
    if (contactToDelete === null) return false;
    const accepted = await contacts.requestDeletion(
      activeOrganizationId,
      contactToDelete.id,
    );
    if (accepted) await contacts.loadCollection(activeOrganizationId, query);
    return accepted;
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="contacts-title">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="contacts-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Contacts
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Manage the organization-owned people agents and products communicate
            with.
          </p>
        </div>
        <Button onClick={() => void navigate(`${basePath}/new`)}>
          <Plus aria-hidden="true" />
          New contact
        </Button>
      </header>
      <CollectionToolbar
        listLabel="Contacts"
        search={
          <form
            className="relative w-full sm:max-w-md"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              updateQuery({
                page: 1,
                search: searchDraft.trim().slice(0, 100),
              });
            }}
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pr-20 pl-9"
              aria-label="Search contacts"
              maxLength={100}
              placeholder="Search identity or contact method"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
            />
            <Button
              className="absolute top-0 right-0 rounded-l-none"
              variant="ghost"
              type="submit"
            >
              Search
            </Button>
          </form>
        }
        filter={
          <FilterControl
            filterTree={query.filters}
            listLabel="Contacts"
            schema={CONTACT_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Contacts"
            options={CONTACT_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) =>
              updateQuery({ direction, page: 1 })
            }
            onSortChange={(sortBy) =>
              updateQuery({
                direction: sortBy.endsWith("_at") ? "desc" : "asc",
                page: 1,
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Contacts"
            schema={CONTACT_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
      />
      <ContactsTable
        query={query}
        onClearFilters={() => setQuery(DEFAULT_CONTACT_QUERY)}
        onDelete={(contact) => {
          contacts.clearDeleteState();
          setContactToDelete(contact);
        }}
        onEdit={edit}
        onPageChange={(page) => updateQuery({ page })}
        onRetry={() =>
          void contacts.loadCollection(activeOrganizationId, query)
        }
        onView={open}
      />
      <ContactDetailsDrawer
        contactId={contactId}
        onClose={() =>
          void navigate({ pathname: basePath, search: location.search })
        }
        onEdit={edit}
      />
      <ContactDeleteDialog
        contact={contactToDelete}
        errorMessage={contacts.deleteErrorMessage}
        isDeleting={contacts.isDeleting}
        job={contacts.deletionJob}
        open={contactToDelete !== null}
        onOpenChange={(next) => {
          if (!next) {
            setContactToDelete(null);
            contacts.clearDeleteState();
          }
        }}
        onConfirm={confirmDelete}
      />
    </section>
  );
});

export { ContactsPage };
