import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { Agent } from "@/features/agents/agents.types";
import { formatSwarmEnum } from "@/features/swarms/swarm-formatters";
import type { SwarmMemberView } from "@/features/swarms/swarms.types";

interface SwarmMembersSectionProps {
  actionErrorMessage: string | null;
  activeAction: string | null;
  availableAgents: readonly Agent[];
  isLoading: boolean;
  members: readonly SwarmMemberView[];
  onAdd: (agentId: string, description: string) => Promise<boolean>;
  onEnsureAgents: () => void;
  onRemove: (agentId: string) => Promise<boolean>;
}

function SwarmMembersSection({
  actionErrorMessage,
  activeAction,
  availableAgents,
  isLoading,
  members,
  onAdd,
  onEnsureAgents,
  onRemove,
}: SwarmMembersSectionProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [description, setDescription] = useState("");
  const memberIds = useMemo(
    () => new Set(members.map(({ mapping }) => mapping.agentId)),
    [members],
  );
  const eligibleAgents = availableAgents.filter(
    (agent) => !memberIds.has(agent.id),
  );
  const selectedAgent = eligibleAgents.find(
    (agent) => agent.id === selectedAgentId,
  );

  function changeDialogOpen(open: boolean): void {
    if (!open && activeAction === "add-member") return;
    setDialogOpen(open);
    if (open) onEnsureAgents();
    else {
      setSelectedAgentId("");
      setDescription("");
    }
  }

  async function addMember(): Promise<void> {
    if (selectedAgentId === "") return;
    if (await onAdd(selectedAgentId, description)) changeDialogOpen(false);
  }

  return (
    <section className="grid gap-5 border p-4 sm:p-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <div>
        <h2 className="text-base font-medium">Topology</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Choose the conversational Agents that can participate in this Swarm.
          Membership changes update the draft immediately.
        </p>
      </div>
      <div className="min-w-0 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium">
            {members.length} {members.length === 1 ? "Agent" : "Agents"}
          </p>
          <Button
            type="button"
            variant="outline"
            disabled={isLoading || activeAction !== null}
            onClick={() => changeDialogOpen(true)}
          >
            <Plus aria-hidden="true" />
            Add Agent
          </Button>
        </div>
        {isLoading ? (
          <div
            className="space-y-2 border p-4"
            aria-label="Loading Swarm Agents"
          >
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : members.length === 0 ? (
          <div className="border p-4">
            <p className="text-sm font-medium">No Agents in this draft</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Add at least one published conversational Agent before publishing
              the Swarm.
            </p>
          </div>
        ) : (
          <div className="divide-y border">
            {members.map(({ agent, mapping }) => {
              const isRemoving =
                activeAction === `remove-member:${mapping.agentId}`;
              return (
                <div
                  className="flex min-w-0 items-start justify-between gap-3 p-4"
                  key={mapping.id}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="break-words text-sm font-medium">
                        {agent?.name ?? mapping.agentId}
                      </p>
                      {agent !== null ? (
                        <Badge variant="outline">
                          {formatSwarmEnum(agent.status)}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm leading-5 break-words text-muted-foreground">
                      {mapping.agentDescription?.trim() ||
                        "No Swarm-specific role description."}
                    </p>
                    {agent !== null ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {agent.lifecycle !== "published" ||
                        agent.publishedRevision == null
                          ? "Agent is not available for new work"
                          : `Agent revision ${agent.publishedRevision} available`}
                      </p>
                    ) : null}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="shrink-0"
                    disabled={activeAction !== null}
                    aria-label={`Remove ${agent?.name ?? mapping.agentId} from Swarm`}
                    title="Remove from draft"
                    onClick={() => void onRemove(mapping.agentId)}
                  >
                    <Trash2 aria-hidden="true" />
                    <span className="sr-only">
                      {isRemoving ? "Removing…" : "Remove"}
                    </span>
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={changeDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Add Agent to Swarm</DialogTitle>
            <DialogDescription>
              Select one organization-owned conversational Agent and describe
              its role in this topology.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="swarm-agent">Agent</Label>
              <Select
                value={selectedAgentId || null}
                disabled={activeAction !== null}
                onValueChange={(value) => setSelectedAgentId(value ?? "")}
              >
                <SelectTrigger id="swarm-agent" className="w-full min-w-0">
                  <SelectValue>
                    {selectedAgent === undefined
                      ? "Choose an Agent"
                      : `${selectedAgent.name} · ${formatSwarmEnum(selectedAgent.status)}`}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {eligibleAgents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.name} · {formatSwarmEnum(agent.status)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {eligibleAgents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No other conversational Agents are available.
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="swarm-agent-description">
                Role in this Swarm
              </Label>
              <Textarea
                id="swarm-agent-description"
                maxLength={2_000}
                rows={4}
                value={description}
                placeholder="Optional context used when this Agent participates in the topology"
                onChange={(event) => setDescription(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                {description.length.toLocaleString()} / 2,000
              </p>
            </div>
            {actionErrorMessage !== null ? (
              <p className="text-sm text-destructive" role="alert">
                {actionErrorMessage}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={activeAction !== null}
              onClick={() => changeDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={selectedAgentId === "" || activeAction !== null}
              onClick={() => void addMember()}
            >
              {activeAction === "add-member" ? "Adding…" : "Add Agent"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export { SwarmMembersSection };
