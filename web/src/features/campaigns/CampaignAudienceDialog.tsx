import { Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useMemo, useState } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  Campaign,
  OrganizationContact,
} from "@/features/campaigns/campaigns.types";

interface CampaignAudienceDialogProps {
  campaign: Campaign;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  organizationId: string;
}

const CampaignAudienceDialog = observer(function CampaignAudienceDialog({
  campaign,
  onOpenChange,
  open,
  organizationId,
}: CampaignAudienceDialogProps) {
  const { campaigns } = useRootStore();
  const [mode, setMode] = useState<"addresses" | "existing">("existing");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [addresses, setAddresses] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const alreadyAdded = useMemo(
    () =>
      new Set(
        campaigns.contacts
          .map((contact) => contact.contactId)
          .filter((id): id is string => id !== null && id !== undefined),
      ),
    [campaigns.contacts],
  );
  const visibleContacts = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return term === ""
      ? campaigns.organizationContacts
      : campaigns.organizationContacts.filter((contact) =>
          [
            contact.name ?? "",
            contact.primaryEmail ?? "",
            contact.primaryPhone ?? "",
            contact.externalId ?? "",
          ]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  }, [campaigns.organizationContacts, search]);

  function close(next: boolean): void {
    if (!next && !campaigns.isActing) {
      setSelectedIds(new Set());
      setSearch("");
      setAddresses("");
      setLocalError(null);
    }
    onOpenChange(next);
  }

  function toggle(id: string, checked: boolean): void {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function submit(): Promise<void> {
    setLocalError(null);
    if (mode === "existing") {
      if (selectedIds.size === 0)
        return setLocalError("Select at least one contact.");
      if (await campaigns.addExistingContacts(organizationId, [...selectedIds]))
        close(false);
      return;
    }
    const parsed = parseAddresses(addresses);
    if (typeof parsed === "string") return setLocalError(parsed);
    if (await campaigns.addAddresses(organizationId, parsed)) close(false);
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Add campaign recipients</DialogTitle>
          <DialogDescription>
            Every selected recipient remains in the filed audience. Eligibility
            policy is not evaluated in V1; the preparation review shows warnings
            before start.
          </DialogDescription>
        </DialogHeader>
        <div
          className="inline-flex w-fit border p-1"
          role="group"
          aria-label="Recipient source"
        >
          <Button
            size="sm"
            variant={mode === "existing" ? "secondary" : "ghost"}
            onClick={() => setMode("existing")}
          >
            Existing contacts
          </Button>
          <Button
            size="sm"
            variant={mode === "addresses" ? "secondary" : "ghost"}
            onClick={() => setMode("addresses")}
          >
            Addresses
          </Button>
        </div>
        {mode === "existing" ? (
          <div className="space-y-3">
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                className="pl-9"
                aria-label="Search organization contacts"
                placeholder="Search contacts"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <div className="max-h-80 divide-y overflow-y-auto border">
              {visibleContacts.length === 0 ? (
                <p className="p-8 text-center text-sm text-muted-foreground">
                  No contacts found
                </p>
              ) : (
                visibleContacts.map((contact) => (
                  <ContactChoice
                    alreadyAdded={alreadyAdded.has(contact.id)}
                    campaign={campaign}
                    checked={selectedIds.has(contact.id)}
                    contact={contact}
                    key={contact.id}
                    onChange={(checked) => toggle(contact.id, checked)}
                  />
                ))
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Showing up to 100 active organization contacts. {selectedIds.size}{" "}
              selected.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <Label htmlFor="campaign-addresses">One address per line</Label>
            <p className="text-xs leading-5 text-muted-foreground">
              Use <code>address</code> or <code>address, name</code>. Voice
              expects phone numbers; email expects email addresses. Invalid
              addresses are recorded as technical rejections, not silently
              removed.
            </p>
            <Textarea
              id="campaign-addresses"
              className="min-h-56 font-mono text-xs"
              placeholder={
                campaign.channel === "voice"
                  ? "+14155550123, Ada"
                  : campaign.channel === "email"
                    ? "ada@example.com, Ada"
                    : "external-id, Ada"
              }
              value={addresses}
              onChange={(event) => setAddresses(event.target.value)}
            />
          </div>
        )}
        {localError === null && campaigns.actionErrorMessage === null ? null : (
          <p className="text-sm text-destructive" role="alert">
            {localError ?? campaigns.actionErrorMessage}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={campaigns.isActing}
            onClick={() => close(false)}
          >
            Cancel
          </Button>
          <Button disabled={campaigns.isActing} onClick={() => void submit()}>
            {campaigns.isActing ? "Adding…" : "Add recipients"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

function ContactChoice({
  alreadyAdded,
  campaign,
  checked,
  contact,
  onChange,
}: {
  alreadyAdded: boolean;
  campaign: Campaign;
  checked: boolean;
  contact: OrganizationContact;
  onChange: (checked: boolean) => void;
}) {
  const address =
    campaign.channel === "voice"
      ? contact.primaryPhone
      : campaign.channel === "email"
        ? contact.primaryEmail
        : (contact.externalId ?? contact.primaryEmail ?? contact.primaryPhone);
  return (
    <label className="grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] gap-3 p-3 hover:bg-muted/50 has-data-disabled:cursor-not-allowed has-data-disabled:bg-muted/30">
      <Checkbox
        className="mt-0.5"
        checked={checked || alreadyAdded}
        disabled={alreadyAdded}
        onCheckedChange={(value) => onChange(value)}
      />
      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-2">
          <span className="break-words text-sm font-medium">
            {contact.name || "Unnamed contact"}
          </span>
          {alreadyAdded ? <Badge variant="outline">Added</Badge> : null}
          {address ? null : (
            <Badge variant="destructive">No channel address</Badge>
          )}
        </span>
        <span className="mt-1 block break-all text-xs text-muted-foreground">
          {address ||
            "This contact will produce a technical rejection if selected."}
        </span>
      </span>
    </label>
  );
}

function parseAddresses(value: string):
  | {
      contactAddress: string;
      name: string | null;
      variables: Record<string, unknown>;
    }[]
  | string {
  const rows = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (rows.length === 0) return "Enter at least one address.";
  if (rows.length > 1000) return "Add at most 1,000 addresses at a time.";
  const recipients = rows
    .map((row) => {
      const comma = row.indexOf(",");
      const contactAddress = (comma === -1 ? row : row.slice(0, comma)).trim();
      const name = comma === -1 ? null : row.slice(comma + 1).trim() || null;
      return { contactAddress, name, variables: name === null ? {} : { name } };
    })
    .filter((row) => row.contactAddress !== "");
  return recipients.length === 0 ? "Enter at least one address." : recipients;
}

export { CampaignAudienceDialog };
