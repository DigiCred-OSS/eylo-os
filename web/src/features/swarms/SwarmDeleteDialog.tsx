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
import type { Swarm } from "@/features/swarms/swarms.types";

interface SwarmDeleteDialogProps {
  errorMessage: string | null;
  isDeleting: boolean;
  onConfirm: () => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  swarm: Swarm | null;
}

function SwarmDeleteDialog({
  errorMessage,
  isDeleting,
  onConfirm,
  onOpenChange,
  open,
  swarm,
}: SwarmDeleteDialogProps) {
  const [confirmation, setConfirmation] = useState("");
  if (swarm === null) return null;

  function changeOpen(nextOpen: boolean): void {
    if (!nextOpen && isDeleting) return;
    if (!nextOpen) setConfirmation("");
    onOpenChange(nextOpen);
  }

  async function confirmDelete(): Promise<void> {
    if (await onConfirm()) setConfirmation("");
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="pr-8">
          <DialogTitle>Delete {swarm.name}?</DialogTitle>
          <DialogDescription>
            This removes the draft Swarm. Type the Swarm name to confirm.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-swarm-confirmation">Swarm name</Label>
          <Input
            id="delete-swarm-confirmation"
            autoComplete="off"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
        </div>
        {errorMessage !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : null}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={isDeleting}
            onClick={() => changeOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={confirmation !== swarm.name || isDeleting}
            onClick={() => void confirmDelete()}
          >
            {isDeleting ? "Deleting…" : "Delete Swarm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { SwarmDeleteDialog };
