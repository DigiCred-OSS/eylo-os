import { useState } from "react";

import { Button } from "@/components/ui/button";
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
import type { Contact, DeletionJob } from "@/features/contacts/contacts.types";

function ContactDeleteDialog({
  contact,
  errorMessage,
  isDeleting,
  job,
  onConfirm,
  onOpenChange,
  open,
}: {
  contact: Contact | null;
  errorMessage: string | null;
  isDeleting: boolean;
  job: DeletionJob | null;
  onConfirm: () => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}) {
  const [confirmation, setConfirmation] = useState("");
  if (contact === null) return null;
  const label = contact.name?.trim() || contact.primaryEmail || contact.id;
  const close = () => {
    if (!isDeleting) {
      setConfirmation("");
      onOpenChange(false);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="pr-8">
          <DialogTitle>
            {job === null
              ? `Request deletion for ${label}?`
              : "Deletion accepted"}
          </DialogTitle>
          <DialogDescription>
            {job === null
              ? "The contact is fenced from new work immediately. Eylo then removes owned contact data asynchronously; campaigns and conversations remain."
              : "The deletion job is now tracked by the platform."}
          </DialogDescription>
        </DialogHeader>
        {job === null ? (
          <div className="space-y-2">
            <Label htmlFor="delete-contact-confirmation">
              Type DELETE to confirm
            </Label>
            <Input
              id="delete-contact-confirmation"
              autoComplete="off"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </div>
        ) : (
          <div className="space-y-2 border p-3 text-sm">
            <p>
              <span className="text-muted-foreground">Job ID:</span>{" "}
              <code className="break-all text-xs">{job.id}</code>
            </p>
            <p>
              <span className="text-muted-foreground">Status:</span>{" "}
              {job.status}
            </p>
          </div>
        )}
        {errorMessage !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : null}
        <DialogFooter>
          {job === null ? (
            <>
              <Button variant="outline" disabled={isDeleting} onClick={close}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={confirmation !== "DELETE" || isDeleting}
                onClick={() => void onConfirm()}
              >
                {isDeleting ? "Requesting…" : "Request deletion"}
              </Button>
            </>
          ) : (
            <Button onClick={close}>Done</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { ContactDeleteDialog };
