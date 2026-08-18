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
import type { Knowledgebase } from "@/features/knowledge/knowledge.types";

interface KnowledgeDeleteDialogProps {
  errorMessage: string | null;
  isDeleting: boolean;
  knowledgebase: Knowledgebase | null;
  onConfirm: () => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}

function KnowledgeDeleteDialog({
  errorMessage,
  isDeleting,
  knowledgebase,
  onConfirm,
  onOpenChange,
  open,
}: KnowledgeDeleteDialogProps) {
  const [confirmation, setConfirmation] = useState("");

  if (knowledgebase === null) {
    return null;
  }

  function changeOpen(nextOpen: boolean): void {
    if (!nextOpen && isDeleting) {
      return;
    }
    if (!nextOpen) {
      setConfirmation("");
    }
    onOpenChange(nextOpen);
  }

  async function confirmDelete(): Promise<void> {
    if (await onConfirm()) {
      setConfirmation("");
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="pr-8">
          <DialogTitle>Delete {knowledgebase.name}?</DialogTitle>
          <DialogDescription>
            This permanently removes indexed content and Agent grants, then
            retires its ingestion and import work. Agents and source storage
            objects are not deleted. Type the knowledgebase name to confirm.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-knowledge-confirmation">
            Knowledgebase name
          </Label>
          <Input
            id="delete-knowledge-confirmation"
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
            disabled={confirmation !== knowledgebase.name || isDeleting}
            onClick={() => void confirmDelete()}
          >
            {isDeleting ? "Deleting…" : "Delete knowledgebase"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { KnowledgeDeleteDialog };
