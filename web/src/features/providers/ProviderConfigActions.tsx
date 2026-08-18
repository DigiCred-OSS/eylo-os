import {
  BadgeCheck,
  CircleOff,
  Ellipsis,
  Pencil,
  Power,
  Trash2,
} from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ProviderConfigRecord } from "@/features/providers/providers.types";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

type ConfirmationAction = "delete" | "toggle" | "verify";

interface ProviderConfigActionsProps {
  config: ProviderConfigRecord;
  onDeleted: () => void;
  onEdit: () => void;
}

const ProviderConfigActions = observer(function ProviderConfigActions({
  config,
  onDeleted,
  onEdit,
}: ProviderConfigActionsProps) {
  const { providers } = useRootStore();
  const [confirmation, setConfirmation] = useState<ConfirmationAction | null>(
    null,
  );
  const [deleteName, setDeleteName] = useState("");
  const contextKey = `${config.capability}:${config.id}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);
  const isPending = providers.pendingAction?.configId === config.id;

  function openConfirmation(action: ConfirmationAction): void {
    providers.clearActionError();
    setDeleteName("");
    setConfirmation(action);
  }

  function closeConfirmation(): void {
    if (isPending) {
      return;
    }
    providers.clearActionError();
    setDeleteName("");
    setConfirmation(null);
  }

  async function confirm(): Promise<void> {
    const submittedContextKey = contextKey;
    let succeeded = false;
    if (confirmation === "verify") {
      succeeded = await providers.verify(config);
    } else if (confirmation === "toggle") {
      succeeded = await providers.setEnabled(config, !config.enabled);
    } else if (confirmation === "delete") {
      succeeded = await providers.delete(config);
    }

    if (!succeeded || !isCurrentContext(submittedContextKey)) {
      return;
    }
    setConfirmation(null);
    setDeleteName("");
    if (confirmation === "delete") {
      onDeleted();
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Actions for ${config.name}`}
              title={`Actions for ${config.name}`}
            />
          }
        >
          <Ellipsis aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={onEdit}>
            <Pencil aria-hidden="true" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => openConfirmation("verify")}>
            <BadgeCheck aria-hidden="true" />
            Verify
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => openConfirmation("toggle")}>
            {config.enabled ? (
              <CircleOff aria-hidden="true" />
            ) : (
              <Power aria-hidden="true" />
            )}
            {config.enabled ? "Disable" : "Enable"}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={() => openConfirmation("delete")}
          >
            <Trash2 aria-hidden="true" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog
        open={confirmation !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeConfirmation();
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>{confirmationTitle(confirmation, config)}</DialogTitle>
            <DialogDescription>
              {confirmationDescription(confirmation, config)}
            </DialogDescription>
          </DialogHeader>

          {confirmation === "delete" ? (
            <div className="space-y-2">
              <Label htmlFor={`delete-provider-${config.id}`}>
                Configuration name
              </Label>
              <Input
                id={`delete-provider-${config.id}`}
                autoComplete="off"
                value={deleteName}
                onChange={(event) => setDeleteName(event.target.value)}
              />
            </div>
          ) : null}

          {providers.actionErrorMessage === null ? null : (
            <p className="text-sm text-destructive" role="alert">
              {providers.actionErrorMessage}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={isPending}
              onClick={closeConfirmation}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant={confirmation === "delete" ? "destructive" : "default"}
              disabled={
                isPending ||
                (confirmation === "delete" && deleteName !== config.name)
              }
              onClick={() => void confirm()}
            >
              {isPending
                ? "Working…"
                : confirmationButtonLabel(confirmation, config)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

function confirmationTitle(
  action: ConfirmationAction | null,
  config: ProviderConfigRecord,
): string {
  if (action === "verify") {
    return `Verify ${config.name}?`;
  }
  if (action === "toggle") {
    return `${config.enabled ? "Disable" : "Enable"} ${config.name}?`;
  }
  return `Delete ${config.name}?`;
}

function confirmationDescription(
  action: ConfirmationAction | null,
  config: ProviderConfigRecord,
): string {
  if (action === "verify") {
    return "Eylo will contact the provider using the stored credentials. A failed check keeps the saved configuration but it will not become ready.";
  }
  if (action === "toggle") {
    return config.enabled
      ? "Disabled configurations remain stored but cannot be selected for new runtime work."
      : "Enabling permits runtime use only when the provider is also verified and ready.";
  }
  return "Deletion is permanent. Referenced configurations are protected by the API and will not be removed. Type the configuration name to confirm.";
}

function confirmationButtonLabel(
  action: ConfirmationAction | null,
  config: ProviderConfigRecord,
): string {
  if (action === "verify") {
    return "Verify provider";
  }
  if (action === "toggle") {
    return config.enabled ? "Disable" : "Enable";
  }
  return "Delete configuration";
}

export { ProviderConfigActions };
