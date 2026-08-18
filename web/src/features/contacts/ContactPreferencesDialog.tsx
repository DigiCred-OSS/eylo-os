import { Plus, Trash2 } from "lucide-react";
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

interface PreferenceRow {
  id: string;
  key: string;
  value: string;
}

function ContactPreferencesDialog({
  onChange,
  onOpenChange,
  open,
  preferences,
}: {
  onChange: (preferences: Record<string, string>) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  preferences: Record<string, string>;
}) {
  const [rows, setRows] = useState<PreferenceRow[]>(() => toRows(preferences));
  const [error, setError] = useState<string | null>(null);

  function changeOpen(nextOpen: boolean): void {
    if (nextOpen) {
      setRows(toRows(preferences));
      setError(null);
    }
    onOpenChange(nextOpen);
  }

  function save(): void {
    const normalized = rows
      .map((row) => ({ key: row.key.trim(), value: row.value.trim() }))
      .filter((row) => row.key !== "");
    if (new Set(normalized.map((row) => row.key)).size !== normalized.length) {
      setError("Preference keys must be unique.");
      return;
    }
    onChange(Object.fromEntries(normalized.map((row) => [row.key, row.value])));
    changeOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Manage preferences</DialogTitle>
          <DialogDescription>
            Store organization-defined key/value context for this contact.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[55dvh] space-y-3 overflow-y-auto pr-1">
          {rows.length === 0 ? (
            <p className="border border-dashed p-4 text-sm text-muted-foreground">
              No preferences added.
            </p>
          ) : (
            rows.map((row, index) => (
              <div
                key={row.id}
                className="grid gap-2 border p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto]"
              >
                <div className="space-y-2">
                  <Label htmlFor={`preference-key-${row.id}`}>Key</Label>
                  <Input
                    id={`preference-key-${row.id}`}
                    maxLength={100}
                    value={row.key}
                    onChange={(event) =>
                      setRows(
                        rows.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, key: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`preference-value-${row.id}`}>Value</Label>
                  <Input
                    id={`preference-value-${row.id}`}
                    maxLength={1000}
                    value={row.value}
                    onChange={(event) =>
                      setRows(
                        rows.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, value: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <Button
                  className="self-end"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove preference ${row.key || index + 1}`}
                  onClick={() =>
                    setRows(rows.filter((_, itemIndex) => itemIndex !== index))
                  }
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            ))
          )}
        </div>
        <Button
          className="w-fit"
          variant="outline"
          onClick={() =>
            setRows([
              ...rows,
              { id: `${Date.now()}-${rows.length}`, key: "", value: "" },
            ])
          }
        >
          <Plus aria-hidden="true" />
          Add preference
        </Button>
        {error !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => changeOpen(false)}>
            Cancel
          </Button>
          <Button onClick={save}>Apply preferences</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function toRows(preferences: Record<string, string>): PreferenceRow[] {
  return Object.entries(preferences).map(([key, value], index) => ({
    id: `${index}-${key}`,
    key,
    value,
  }));
}

export { ContactPreferencesDialog };
