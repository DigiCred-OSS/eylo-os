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
import type { Agent } from "@/features/agents/agents.types";

interface AgentDeleteDialogProps {
  agent: Agent | null;
  errorMessage: string | null;
  isDeleting: boolean;
  onConfirm: () => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}

function AgentDeleteDialog({
  agent,
  errorMessage,
  isDeleting,
  onConfirm,
  onOpenChange,
  open,
}: AgentDeleteDialogProps) {
  const [confirmation, setConfirmation] = useState("");

  if (agent === null) {
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
          <DialogTitle>Delete {agent.name}?</DialogTitle>
          <DialogDescription>
            This removes the draft Agent from the collection. Type the Agent
            name to confirm.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-agent-confirmation">Agent name</Label>
          <Input
            id="delete-agent-confirmation"
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
            disabled={confirmation !== agent.name || isDeleting}
            onClick={() => void confirmDelete()}
          >
            {isDeleting ? "Deleting…" : "Delete Agent"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { AgentDeleteDialog };
