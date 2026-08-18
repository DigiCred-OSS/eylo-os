import { Check, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
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
import type { AgentFormValues } from "@/features/agents/agents.types";
import { voiceRuntimeMode } from "@/features/voice/voice.query";
import { cn } from "@/lib/utils";

interface AgentVoiceSectionProps {
  onChange: (voiceConfigId: string | null) => void;
  organizationId: string;
  values: AgentFormValues;
}

const AgentVoiceSection = observer(function AgentVoiceSection({
  onChange,
  organizationId,
  values,
}: AgentVoiceSectionProps) {
  const { voice } = useRootStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    void voice.loadCollection(organizationId);
  }, [organizationId, voice]);

  const selected =
    voice.items.find((item) => item.id === values.voiceConfigId) ?? null;
  const options = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase();
    return normalized === ""
      ? voice.items
      : voice.items.filter((item) =>
          [item.name, item.description ?? ""]
            .join(" ")
            .toLocaleLowerCase()
            .includes(normalized),
        );
  }, [search, voice.items]);

  if (values.kind === "BACKGROUND") {
    return (
      <section className="border bg-card p-5">
        <h2 className="text-lg font-semibold">Voice</h2>
        <p className="mt-1 text-sm leading-5 text-muted-foreground">
          Background Agents do not participate in live voice conversations and
          cannot bind a Voice Config.
        </p>
      </section>
    );
  }

  function manageVoiceConfigs(): void {
    const returnTo = `${location.pathname}${location.search}`;
    void navigate(
      `/org/${organizationId}/voice?returnTo=${encodeURIComponent(returnTo)}`,
    );
  }

  return (
    <section className="space-y-5 border bg-card p-5">
      <div>
        <h2 className="text-lg font-semibold">Voice</h2>
        <p className="mt-1 max-w-2xl text-sm leading-5 text-muted-foreground">
          Bind one reusable Voice Config. Publication pins its exact revision
          and provider revisions into this Agent revision.
        </p>
      </div>

      <div className="flex flex-col gap-4 border p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {selected?.name ??
              (values.voiceConfigId === null
                ? "No Voice Config"
                : "Selected Voice Config")}
          </p>
          {selected === null ? (
            <p className="mt-1 break-all text-sm text-muted-foreground">
              {values.voiceConfigId === null
                ? "This Agent is text-only."
                : values.voiceConfigId}
            </p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="outline">
                {voiceRuntimeMode(selected) === "realtime"
                  ? "Realtime"
                  : "Decomposed"}
              </Badge>
              <Badge variant="outline">Revision {selected.revision}</Badge>
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {values.voiceConfigId === null ? null : (
            <Button
              type="button"
              variant="ghost"
              onClick={() => onChange(null)}
            >
              Clear
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setSearch("");
              setOpen(true);
              void voice.loadCollection(organizationId);
            }}
          >
            {values.voiceConfigId === null ? "Choose" : "Change"}
          </Button>
        </div>
      </div>

      <div className="border bg-muted/20 p-4 text-sm leading-5 text-muted-foreground">
        Swarm rule: when this Agent starts a call as the primary Agent, its
        published Voice Config stays active for the entire conversation.
        Handoffs change Agent context and tools; they never switch voice or
        providers mid-call.
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Choose a Voice Config</DialogTitle>
            <DialogDescription>
              The current config revision is bound now; publication resolves and
              pins ready provider revisions.
            </DialogDescription>
          </DialogHeader>
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pl-9"
              aria-label="Search Voice Configs"
              placeholder="Search Voice Configs"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="max-h-80 min-h-36 overflow-y-auto border">
            {voice.isCollectionLoading && voice.items.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                Loading Voice Configs…
              </p>
            ) : voice.collectionErrorMessage !== null &&
              voice.items.length === 0 ? (
              <div className="p-6 text-center">
                <p className="text-sm text-destructive">
                  {voice.collectionErrorMessage}
                </p>
                <Button
                  className="mt-3"
                  type="button"
                  variant="outline"
                  onClick={() => void voice.loadCollection(organizationId)}
                >
                  Try again
                </Button>
              </div>
            ) : options.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                {voice.items.length === 0
                  ? "No Voice Configs are available."
                  : "No Voice Configs match this search."}
              </p>
            ) : (
              <div className="divide-y">
                {options.map((option) => {
                  const isSelected = option.id === values.voiceConfigId;
                  return (
                    <button
                      key={option.id}
                      className={cn(
                        "grid w-full grid-cols-[1fr_auto] gap-4 p-3 text-left transition-colors hover:bg-muted focus-visible:outline-2",
                        isSelected && "bg-muted",
                      )}
                      type="button"
                      onClick={() => {
                        onChange(option.id);
                        setOpen(false);
                      }}
                    >
                      <span className="min-w-0">
                        <span className="block break-words text-sm font-medium">
                          {option.name}
                        </span>
                        <span className="mt-0.5 block break-words text-xs text-muted-foreground">
                          {voiceRuntimeMode(option) === "realtime"
                            ? "Realtime"
                            : "Decomposed"}
                          {` · revision ${option.revision}`}
                        </span>
                      </span>
                      {isSelected ? (
                        <Check className="size-4" aria-hidden="true" />
                      ) : null}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={manageVoiceConfigs}
            >
              Manage Voice Configs
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
});

export { AgentVoiceSection };
