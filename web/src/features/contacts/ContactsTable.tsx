import { Ellipsis, Eye, Pencil, Trash2 } from "lucide-react";
import { observer } from "mobx-react-lite";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatContactDate,
  formatContactLifecycle,
} from "@/features/contacts/contact-formatters";
import { hasContactCollectionFilters } from "@/features/contacts/contacts.query";
import type {
  Contact,
  ContactCollectionQuery,
} from "@/features/contacts/contacts.types";

interface ContactsTableProps {
  onClearFilters: () => void;
  onDelete: (contact: Contact) => void;
  onEdit: (contactId: string) => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onView: (contactId: string) => void;
  query: ContactCollectionQuery;
}

const ContactsTable = observer(function ContactsTable({
  onClearFilters,
  onDelete,
  onEdit,
  onPageChange,
  onRetry,
  onView,
  query,
}: ContactsTableProps) {
  const { contacts } = useRootStore();
  if (contacts.collectionErrorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Contacts are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {contacts.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }
  const hasFilters = hasContactCollectionFilters(query);
  if (!contacts.isCollectionLoading && contacts.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No contacts match these filters" : "No contacts yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to see other contacts."
            : "Create a contact to make it available to agents and products."}
        </p>
        {hasFilters ? (
          <Button className="mt-4" variant="outline" onClick={onClearFilters}>
            Clear filters
          </Button>
        ) : null}
      </div>
    );
  }
  return (
    <div className="border">
      <div className="divide-y sm:hidden" role="list" aria-label="Contacts">
        {contacts.isCollectionLoading
          ? Array.from({ length: 5 }, (_, index) => (
              <ContactLoadingCard key={index} />
            ))
          : contacts.items.map((contact) => (
              <ContactCard
                key={contact.id}
                contact={contact}
                onDelete={onDelete}
                onEdit={onEdit}
                onView={onView}
              />
            ))}
      </div>
      <Table className="hidden sm:table" aria-label="Contacts">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Contact</TableHead>
            <TableHead className="hidden md:table-cell">Phone</TableHead>
            <TableHead>Lifecycle</TableHead>
            <TableHead className="hidden lg:table-cell">Updated</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {contacts.isCollectionLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <ContactLoadingRow key={index} />
              ))
            : contacts.items.map((contact) => (
                <ContactRow
                  key={contact.id}
                  contact={contact}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="flex min-h-14 items-center justify-between gap-4 border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          {paginationLabel(
            contacts.page,
            contacts.limit,
            contacts.items.length,
            contacts.total,
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={contacts.isCollectionLoading || contacts.page <= 1}
            onClick={() => onPageChange(contacts.page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={contacts.isCollectionLoading || !contacts.hasMore}
            onClick={() => onPageChange(contacts.page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
});

function ContactRow({
  contact,
  onDelete,
  onEdit,
  onView,
}: ContactActionsProps) {
  return (
    <TableRow>
      <TableCell className="max-w-md whitespace-normal">
        <button
          className="max-w-full text-left font-medium break-words underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(contact.id)}
        >
          {contact.name?.trim() ||
            contact.primaryEmail ||
            contact.primaryPhone ||
            "Unnamed contact"}
        </button>
        <p className="mt-0.5 break-all text-xs text-muted-foreground">
          {contact.primaryEmail ??
            contact.externalId ??
            "No email or external ID"}
        </p>
      </TableCell>
      <TableCell className="hidden break-all text-muted-foreground md:table-cell">
        {contact.primaryPhone ?? "Not provided"}
      </TableCell>
      <TableCell>
        <Badge variant="outline">
          {formatContactLifecycle(contact.lifecycle)}
        </Badge>
      </TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">
        <DateValue value={contact.updatedAt} />
      </TableCell>
      <TableCell className="text-right">
        <ContactActions
          contact={contact}
          onDelete={onDelete}
          onEdit={onEdit}
          onView={onView}
        />
      </TableCell>
    </TableRow>
  );
}

function ContactCard({
  contact,
  onDelete,
  onEdit,
  onView,
}: ContactActionsProps) {
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            className="max-w-full text-left font-medium break-words underline-offset-4 hover:underline"
            type="button"
            onClick={() => onView(contact.id)}
          >
            {contact.name?.trim() ||
              contact.primaryEmail ||
              contact.primaryPhone ||
              "Unnamed contact"}
          </button>
          <p className="mt-1 break-all text-sm text-muted-foreground">
            {contact.primaryEmail ?? "No email"}
          </p>
        </div>
        <ContactActions
          contact={contact}
          onDelete={onDelete}
          onEdit={onEdit}
          onView={onView}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">
          {formatContactLifecycle(contact.lifecycle)}
        </Badge>
        <span>{contact.primaryPhone ?? "No phone"}</span>
        <span>Updated {formatContactDate(contact.updatedAt).label}</span>
      </div>
    </article>
  );
}

interface ContactActionsProps {
  contact: Contact;
  onDelete: (contact: Contact) => void;
  onEdit: (id: string) => void;
  onView: (id: string) => void;
}
function ContactActions({
  contact,
  onDelete,
  onEdit,
  onView,
}: ContactActionsProps) {
  const pending = contact.lifecycle === "deletion_pending";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${contact.name ?? contact.id}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <DropdownMenuItem onClick={() => onView(contact.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
        <DropdownMenuItem disabled={pending} onClick={() => onEdit(contact.id)}>
          <Pencil aria-hidden="true" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem
          className="text-destructive"
          disabled={pending}
          onClick={() => onDelete(contact)}
        >
          <Trash2 aria-hidden="true" />
          Request deletion
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function DateValue({ value }: { value: string | null | undefined }) {
  const formatted = formatContactDate(value);
  return formatted.exact === null ? (
    formatted.label
  ) : (
    <time dateTime={formatted.exact}>{formatted.label}</time>
  );
}
function paginationLabel(
  page: number,
  limit: number,
  count: number,
  total: number,
) {
  if (count === 0) return "No contacts";
  const first = (page - 1) * limit + 1;
  return `${first}–${first + count - 1} of ${total} contacts`;
}
function ContactLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-48" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}
function ContactLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-36" />
      <Skeleton className="h-3 w-48" />
      <Skeleton className="h-5 w-20" />
    </div>
  );
}

export { ContactsTable };
