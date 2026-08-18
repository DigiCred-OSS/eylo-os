import { ArrowLeft, ListPlus, RotateCcw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ContactPreferencesDialog } from "@/features/contacts/ContactPreferencesDialog";
import { formatContactDate } from "@/features/contacts/contact-formatters";
import type {
  ContactFormMode,
  ContactFormValues,
} from "@/features/contacts/contacts.types";

const ContactFormPage = observer(function ContactFormPage({
  mode,
}: {
  mode: ContactFormMode;
}) {
  const { auth, contacts } = useRootStore();
  const { contactId, organizationId } = useParams();
  const navigate = useNavigate();
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const form = contacts.form;
  const memberKey = auth.member?.email ?? "unknown-member";

  useEffect(() => {
    if (organizationId === undefined) return;
    if (mode === "create") form.beginCreate({ memberKey, organizationId });
    else if (contactId !== undefined)
      void form.beginEdit({ contactId, memberKey, organizationId });
  }, [contactId, form, memberKey, mode, organizationId]);

  if (organizationId === undefined) return null;
  const collectionPath = `/org/${organizationId}/contacts`;
  const formContext = {
    contactId: mode === "edit" ? (contactId ?? null) : null,
    memberKey,
    mode,
    organizationId,
  };
  const contextReady = form.isActiveFor(formContext);
  const editUnavailable =
    contextReady &&
    mode === "edit" &&
    !form.isLoading &&
    form.serverContact === null;
  const setField = <Field extends keyof ContactFormValues>(
    field: Field,
    value: ContactFormValues[Field],
  ) => form.setField(field, value);
  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    const saved = await form.submit();
    if (saved !== null)
      void navigate(`${collectionPath}/${saved.id}`, { replace: true });
  }

  return (
    <section
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
      aria-labelledby="contact-form-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <Button
            className="-ml-3"
            variant="ghost"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Contacts
          </Button>
          <div>
            <h1
              id="contact-form-title"
              className="text-2xl font-semibold tracking-tight"
            >
              {mode === "create" ? "New contact" : "Edit contact"}
            </h1>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              {mode === "create"
                ? "Create organization-owned contact identity for agents and products."
                : "Update maintained identity, contact methods, and preferences."}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {form.hasLocalDraft ? (
            <span className="text-xs text-muted-foreground">
              Draft saved locally {formatContactDate(form.savedAt).label}
            </span>
          ) : null}
          <Button
            variant="outline"
            disabled={!contextReady || form.isLoading || editUnavailable}
            onClick={() =>
              mode === "create"
                ? form.startNew({ memberKey, organizationId })
                : form.discardLocalDraft()
            }
          >
            <RotateCcw aria-hidden="true" />
            {mode === "create" ? "Start new" : "Discard draft"}
          </Button>
        </div>
      </header>
      {!contextReady || form.isLoading ? (
        <FormSkeleton />
      ) : editUnavailable ? (
        <div className="space-y-4 border border-destructive/30 bg-destructive/5 p-4 sm:p-5">
          <p className="text-sm text-destructive" role="alert">
            {form.errorMessage ??
              "This contact could not be loaded. It may no longer exist."}
          </p>
          <Button
            variant="outline"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Back to contacts
          </Button>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={(event) => void submit(event)}>
          <FormSection
            title="Identity"
            description="How this contact is recognized inside the organization."
          >
            <FormField
              id="contact-name"
              label="Name"
              error={form.fieldErrors.name}
            >
              <Input
                id="contact-name"
                maxLength={255}
                value={form.values.name}
                aria-invalid={form.fieldErrors.name !== undefined}
                onChange={(event) => setField("name", event.target.value)}
              />
            </FormField>
            <FormField
              id="contact-external-id"
              label="External ID"
              description="Optional identity supplied by your source system."
              error={form.fieldErrors.externalId}
            >
              <Input
                id="contact-external-id"
                maxLength={1000}
                value={form.values.externalId}
                aria-invalid={form.fieldErrors.externalId !== undefined}
                onChange={(event) => setField("externalId", event.target.value)}
              />
            </FormField>
          </FormSection>
          <FormSection
            title="Contact methods"
            description="At least one contact method is useful, but the platform does not invent one."
          >
            <FormField
              id="contact-email"
              label="Primary email"
              error={form.fieldErrors.primaryEmail}
            >
              <Input
                id="contact-email"
                inputMode="email"
                autoComplete="email"
                maxLength={320}
                value={form.values.primaryEmail}
                aria-invalid={form.fieldErrors.primaryEmail !== undefined}
                onChange={(event) =>
                  setField("primaryEmail", event.target.value)
                }
              />
            </FormField>
            <FormField
              id="contact-phone"
              label="Primary phone"
              description="Use E.164 format, for example +14155552671."
              error={form.fieldErrors.primaryPhone}
            >
              <Input
                id="contact-phone"
                inputMode="tel"
                autoComplete="tel"
                maxLength={16}
                value={form.values.primaryPhone}
                aria-invalid={form.fieldErrors.primaryPhone !== undefined}
                onChange={(event) =>
                  setField("primaryPhone", event.target.value)
                }
              />
            </FormField>
          </FormSection>
          <FormSection
            title="Preferences"
            description="Optional organization-defined context stored as key/value pairs."
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border p-4">
              <div>
                <p className="text-sm font-medium">
                  {Object.keys(form.values.preferences).length === 0
                    ? "No preferences"
                    : `${Object.keys(form.values.preferences).length} ${Object.keys(form.values.preferences).length === 1 ? "preference" : "preferences"}`}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Use the mapping editor to add or update values.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPreferencesOpen(true)}
              >
                <ListPlus aria-hidden="true" />
                Manage preferences
              </Button>
            </div>
          </FormSection>
          {form.errorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
              role="alert"
            >
              {form.errorMessage}
            </div>
          ) : null}
          {form.draftStorageErrorMessage !== null ? (
            <div className="border p-3 text-sm" role="alert">
              {form.draftStorageErrorMessage}
            </div>
          ) : null}
          <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={form.isSubmitting}
              onClick={() => void navigate(collectionPath)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={form.isSubmitting}>
              {form.isSubmitting
                ? "Saving…"
                : mode === "create"
                  ? "Create contact"
                  : "Save contact"}
            </Button>
          </div>
        </form>
      )}
      {preferencesOpen ? (
        <ContactPreferencesDialog
          open
          preferences={form.values.preferences}
          onOpenChange={setPreferencesOpen}
          onChange={(preferences) => setField("preferences", preferences)}
        />
      ) : null}
    </section>
  );
});

function FormSection({
  children,
  description,
  title,
}: {
  children: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <section className="grid gap-5 border p-4 sm:p-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <div>
        <h2 className="text-base font-medium">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
      <div className="min-w-0 space-y-5">{children}</div>
    </section>
  );
}
function FormField({
  children,
  description,
  error,
  id,
  label,
}: {
  children: React.ReactNode;
  description?: string;
  error?: string;
  id: string;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {description ? (
        <p className="text-xs leading-5 text-muted-foreground">{description}</p>
      ) : null}
      {children}
      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
function FormSkeleton() {
  return (
    <div className="space-y-6">
      <div className="border p-5">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="mt-6 h-9 w-full" />
        <Skeleton className="mt-5 h-9 w-full" />
      </div>
      <div className="border p-5">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="mt-6 h-9 w-full" />
        <Skeleton className="mt-5 h-9 w-full" />
      </div>
    </div>
  );
}

export { ContactFormPage };
