import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { VoiceConfigRecord } from "@/features/voice/voice.types";

function VoiceConfigDeleteDialog({
  errorMessage,
  isDeleting,
  onConfirm,
  onOpenChange,
  open,
  voiceConfig,
}: {
  errorMessage: string | null;
  isDeleting: boolean;
  onConfirm: () => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  voiceConfig: VoiceConfigRecord | null;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this Voice Config?</DialogTitle>
          <DialogDescription>
            {voiceConfig === null
              ? "This action cannot be undone."
              : `“${voiceConfig.name}” can be deleted only when no Agent is bound to it.`}
          </DialogDescription>
        </DialogHeader>
        {errorMessage === null ? null : (
          <div
            className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
            role="alert"
          >
            {errorMessage}
          </div>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={isDeleting}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={voiceConfig === null || isDeleting}
            onClick={() => void onConfirm()}
          >
            {isDeleting ? "Deleting…" : "Delete Voice Config"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { VoiceConfigDeleteDialog };
