import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { CuratedConnection } from "@/features/integrations/integrations.types";

interface ConnectionDeleteDialogProps {
  connection: CuratedConnection | null;
  errorMessage: string | null;
  isDeleting: boolean;
  onConfirm: () => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  vendorName: string;
}

function ConnectionDeleteDialog({
  connection,
  errorMessage,
  isDeleting,
  onConfirm,
  onOpenChange,
  vendorName,
}: ConnectionDeleteDialogProps) {
  if (connection === null) return null;

  function changeOpen(nextOpen: boolean): void {
    if (!nextOpen && !isDeleting) onOpenChange(false);
  }

  return (
    <Dialog open onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="pr-8">
          <DialogTitle>Delete connection?</DialogTitle>
          <DialogDescription>
            Eylo will clear this stored credential and remove the connection
            from the list. The vendor configuration, tools, Agents, and other
            connections remain. This does not revoke the credential at{" "}
            {vendorName}.
          </DialogDescription>
        </DialogHeader>
        <p className="break-words text-sm text-muted-foreground">
          {vendorName} · {connection.owner.displayName}
        </p>
        {errorMessage ? (
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
            disabled={isDeleting}
            onClick={() => void onConfirm()}
          >
            {isDeleting ? "Deleting…" : "Delete connection"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { ConnectionDeleteDialog };
