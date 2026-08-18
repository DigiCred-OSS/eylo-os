import { Check, Pencil, Plus, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";

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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatAgentDate } from "@/features/agents/agent-formatters";
import type { AgentInstructionTemplate } from "@/features/agents/agents.types";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

interface AgentInstructionFieldProps {
  agentId: string | null;
  memberKey: string;
  onChange: (value: string | null) => void;
  organizationId: string;
  value: string | null;
}

type DialogView = "editor" | "list";

const AgentInstructionField = observer(function AgentInstructionField({
  agentId,
  memberKey,
  onChange,
  organizationId,
  value,
}: AgentInstructionFieldProps) {
  const { agents } = useRootStore();
  const instructions = agents.instructions;
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<DialogView>("list");
  const selectionContextKey = `${organizationId}:${agentId ?? "new"}`;
  const isCurrentContext = useAsyncContextGuard(selectionContextKey);
  const selected = instructions.templateFor(value);
  const filteredTemplates = useMemo(
    () => filterTemplates(instructions.items, search),
    [instructions.items, search],
  );

  useEffect(() => {
    void instructions.load(organizationId);
  }, [instructions, organizationId]);

  function setOpen(open: boolean): void {
    if (!open && instructions.isSaving) {
      return;
    }
    setIsOpen(open);
    if (open) {
      setSearch("");
      setView(instructions.hasEditor ? "editor" : "list");
      void instructions.load(organizationId, true);
    }
  }

  function beginCreate(): void {
    instructions.beginCreate(memberKey, organizationId);
    setView("editor");
  }

  function beginEdit(template: AgentInstructionTemplate): void {
    instructions.beginEdit(memberKey, organizationId, template);
    setView("editor");
  }

  async function publishAndSelect(): Promise<void> {
    const submittedContextKey = selectionContextKey;
    const templateId = await instructions.publishAndSelect();
    if (
      templateId === null ||
      !isCurrentContext(submittedContextKey) ||
      !agents.form.matchesContext(organizationId, agentId)
    ) {
      return;
    }
    onChange(templateId);
    setIsOpen(false);
    setView("list");
  }

  return (
    <div className="flex flex-col gap-4 border p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="text-sm font-medium">Instruction template</p>
        <p className="mt-1 text-sm leading-5 text-muted-foreground">
          Published instructions used by this Agent's next revision.
        </p>
        <p className="mt-2 truncate text-xs text-muted-foreground">
          {value === null
            ? "Not configured"
            : selected === null
              ? `Selected: ${value}`
              : `${selected.name} · published revision ${selected.published_revision}`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {value !== null ? (
          <Button type="button" variant="ghost" onClick={() => onChange(null)}>
            Clear
          </Button>
        ) : null}
        <Button
          type="button"
          variant="outline"
          disabled={instructions.isSaving}
          onClick={() => setOpen(true)}
        >
          {value === null ? "Choose or create" : "Change"}
        </Button>
      </div>

      <Dialog open={isOpen} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-2xl">
          {view === "list" ? (
            <InstructionList
              errorMessage={instructions.errorMessage}
              isLoading={instructions.isLoading}
              search={search}
              selectedId={value}
              templates={filteredTemplates}
              onCreate={beginCreate}
              onEdit={beginEdit}
              onSearchChange={setSearch}
              onSelect={(templateId) => {
                onChange(templateId);
                setIsOpen(false);
              }}
            />
          ) : (
            <InstructionEditor
              instructions={instructions}
              onBack={() => setView("list")}
              onDiscard={() => {
                instructions.discardEditor();
                setView("list");
              }}
              onPublish={() => void publishAndSelect()}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
});

function InstructionList({
  errorMessage,
  isLoading,
  onCreate,
  onEdit,
  onSearchChange,
  onSelect,
  search,
  selectedId,
  templates,
}: {
  errorMessage: string | null;
  isLoading: boolean;
  onCreate: () => void;
  onEdit: (template: AgentInstructionTemplate) => void;
  onSearchChange: (value: string) => void;
  onSelect: (templateId: string) => void;
  search: string;
  selectedId: string | null;
  templates: AgentInstructionTemplate[];
}) {
  return (
    <>
      <DialogHeader className="pr-8">
        <DialogTitle>Choose Agent instructions</DialogTitle>
        <DialogDescription>
          Select a published template or author and publish one here. Eylo does
          not supply default instructions.
        </DialogDescription>
      </DialogHeader>

      <div className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            className="pl-9"
            aria-label="Search Agent instructions"
            placeholder="Search instructions"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <Button type="button" onClick={onCreate}>
          <Plus aria-hidden="true" />
          New
        </Button>
      </div>

      <div className="max-h-80 min-h-44 divide-y overflow-y-auto border">
        {isLoading && templates.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            Loading instructions…
          </p>
        ) : errorMessage !== null && templates.length === 0 ? (
          <p className="p-6 text-center text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : templates.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            No instruction templates match this search.
          </p>
        ) : (
          templates.map((template) => {
            const isPublished = template.published_revision !== null;
            return (
              <div
                key={template.id}
                className="grid gap-3 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-medium">
                      {template.name}
                    </p>
                    <Badge variant="outline">
                      {isPublished
                        ? `Revision ${template.published_revision}`
                        : "Not published"}
                    </Badge>
                    {template.draft_dirty ? (
                      <Badge variant="secondary">Draft changes</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {template.draft_body}
                  </p>
                </div>
                <div className="flex items-center justify-end gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onEdit(template)}
                  >
                    <Pencil aria-hidden="true" />
                    {isPublished ? "Edit" : "Finish"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    disabled={!isPublished}
                    variant={
                      selectedId === template.id ? "secondary" : "outline"
                    }
                    onClick={() => onSelect(template.id)}
                  >
                    {selectedId === template.id ? (
                      <Check aria-hidden="true" />
                    ) : null}
                    {selectedId === template.id ? "Selected" : "Select"}
                  </Button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <DialogFooter showCloseButton />
    </>
  );
}

type InstructionsStore = ReturnType<
  typeof useRootStore
>["agents"]["instructions"];

const InstructionEditor = observer(function InstructionEditor({
  instructions,
  onBack,
  onDiscard,
  onPublish,
}: {
  instructions: InstructionsStore;
  onBack: () => void;
  onDiscard: () => void;
  onPublish: () => void;
}) {
  const template = instructions.templateFor(instructions.templateId);
  const canPublish =
    instructions.name.trim() !== "" &&
    instructions.body.trim() !== "" &&
    instructions.conflictMessage === null &&
    (instructions.isCreating ||
      template?.published_revision === null ||
      instructions.isEditorDirty);

  return (
    <>
      <DialogHeader className="pr-8">
        <DialogTitle>
          {instructions.isCreating
            ? "New Agent instructions"
            : "Edit Agent instructions"}
        </DialogTitle>
        <DialogDescription>
          Publishing creates the immutable revision the Agent can bind. Runtime
          variables are not supported for Agent instructions in V1.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-5">
        {instructions.conflictMessage !== null ? (
          <div
            className="border border-warning/40 bg-warning/5 p-3"
            role="alert"
          >
            <p className="text-sm text-warning">
              {instructions.conflictMessage}
            </p>
            <Button
              className="mt-3"
              type="button"
              size="sm"
              variant="outline"
              onClick={instructions.rebaseEditor}
            >
              Keep my text on latest draft
            </Button>
          </div>
        ) : null}
        {instructions.actionErrorMessage !== null ? (
          <p
            className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
            role="alert"
          >
            {instructions.actionErrorMessage}
          </p>
        ) : null}
        {instructions.draftStorageErrorMessage !== null ? (
          <p className="border p-3 text-sm text-muted-foreground" role="status">
            {instructions.draftStorageErrorMessage}
          </p>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="agent-instruction-name">Name</Label>
          <Input
            id="agent-instruction-name"
            required
            maxLength={128}
            autoComplete="off"
            disabled={!instructions.isCreating || instructions.isSaving}
            value={instructions.name}
            onChange={(event) => instructions.setName(event.target.value)}
          />
          {!instructions.isCreating ? (
            <p className="text-xs text-muted-foreground">
              Template names are immutable in the current API.
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="agent-instruction-body">Instructions</Label>
          <Textarea
            id="agent-instruction-body"
            required
            rows={14}
            maxLength={64_000}
            disabled={instructions.isSaving}
            value={instructions.body}
            onChange={(event) => instructions.setBody(event.target.value)}
          />
          <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
            <span>
              {instructions.savedAt === null
                ? "Not saved locally"
                : `Saved locally ${formatAgentDate(instructions.savedAt)}`}
            </span>
            <span>{instructions.body.length.toLocaleString()} / 64,000</span>
          </div>
        </div>
      </div>

      <DialogFooter className="flex-wrap sm:justify-between">
        <Button
          type="button"
          variant="ghost"
          disabled={instructions.isSaving}
          onClick={onDiscard}
        >
          Discard local edit
        </Button>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={instructions.isSaving}
            onClick={onBack}
          >
            Back
          </Button>
          <Button
            type="button"
            disabled={!canPublish || instructions.isSaving}
            onClick={onPublish}
          >
            {instructions.isSaving ? "Publishing…" : "Publish and select"}
          </Button>
        </div>
      </DialogFooter>
    </>
  );
});

function filterTemplates(
  templates: readonly AgentInstructionTemplate[],
  search: string,
): AgentInstructionTemplate[] {
  const normalized = search.trim().toLowerCase();
  return normalized === ""
    ? [...templates]
    : templates.filter((template) =>
        `${template.name} ${template.draft_body}`
          .toLowerCase()
          .includes(normalized),
      );
}

export { AgentInstructionField };
