import { ArrowRight, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

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
import { Input } from "@/components/ui/input";

interface KnowledgeAgentAccessDialogProps {
  knowledgebaseName: string;
  open: boolean;
  organizationId: string;
  returnTo: string;
  writable: boolean;
  onOpenChange: (open: boolean) => void;
}

const KnowledgeAgentAccessDialog = observer(
  function KnowledgeAgentAccessDialog({
    knowledgebaseName,
    onOpenChange,
    open,
    organizationId,
    returnTo,
    writable,
  }: KnowledgeAgentAccessDialogProps) {
    const { knowledge } = useRootStore();
    const navigate = useNavigate();
    const [search, setSearch] = useState("");
    const visibleOptions = useMemo(() => {
      const normalized = search.trim().toLowerCase();
      return normalized === ""
        ? knowledge.agentOptions
        : knowledge.agentOptions.filter((agent) =>
            `${agent.label} ${agent.kind} ${agent.lifecycle}`
              .toLowerCase()
              .includes(normalized),
          );
    }, [knowledge.agentOptions, search]);

    useEffect(() => {
      if (!open) {
        return;
      }
      setSearch("");
      void knowledge.loadAgentOptions(organizationId, true);
    }, [knowledge, open, organizationId]);

    function setOpen(nextOpen: boolean): void {
      onOpenChange(nextOpen);
    }

    function configureAgent(agentId: string): void {
      const params = new URLSearchParams({
        returnTo,
        section: "relationships",
      });
      void navigate({
        pathname: `/org/${organizationId}/agents/${agentId}/edit`,
        search: `?${params.toString()}`,
      });
    }

    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Configure Agent access</DialogTitle>
            <DialogDescription>
              Choose an Agent, then grant {knowledgebaseName} from its
              Relationships section.{" "}
              {writable
                ? "Read or read-write access is available."
                : "This knowledgebase is read-only."}
            </DialogDescription>
          </DialogHeader>

          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pl-9"
              aria-label="Search Agents"
              placeholder="Search Agents"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="max-h-80 min-h-36 overflow-y-auto border">
            {knowledge.isAgentOptionsLoading &&
            knowledge.agentOptions.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                Loading Agents…
              </p>
            ) : knowledge.agentOptionsErrorMessage !== null ? (
              <div className="p-6 text-center" role="alert">
                <p className="text-sm text-destructive">
                  {knowledge.agentOptionsErrorMessage}
                </p>
                <Button
                  className="mt-3"
                  variant="outline"
                  onClick={() =>
                    void knowledge.loadAgentOptions(organizationId, true)
                  }
                >
                  Try again
                </Button>
              </div>
            ) : visibleOptions.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                {knowledge.agentOptions.length === 0
                  ? "No Agents exist in this organization."
                  : "No Agents match this search."}
              </p>
            ) : (
              <div className="divide-y">
                {visibleOptions.map((agent) => (
                  <button
                    key={agent.id}
                    className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-3 text-left transition-colors hover:bg-muted focus-visible:outline-2"
                    type="button"
                    onClick={() => configureAgent(agent.id)}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {agent.label}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {agent.kind.toLowerCase()} · {agent.lifecycle}
                      </span>
                    </span>
                    <ArrowRight
                      className="size-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </button>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  },
);

export { KnowledgeAgentAccessDialog };
