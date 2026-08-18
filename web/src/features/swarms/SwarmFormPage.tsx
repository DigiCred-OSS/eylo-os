import { ArrowLeft, RotateCcw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { formatSwarmDate } from "@/features/swarms/swarm-formatters";
import { SwarmLifecycleSection } from "@/features/swarms/SwarmLifecycleSection";
import { SwarmMembersSection } from "@/features/swarms/SwarmMembersSection";
import type {
  SwarmFormMode,
  SwarmFormValues,
} from "@/features/swarms/swarms.types";

const SwarmFormPage = observer(function SwarmFormPage({
  mode,
}: {
  mode: SwarmFormMode;
}) {
  const { auth, swarms } = useRootStore();
  const { organizationId, swarmId } = useParams();
  const navigate = useNavigate();
  const form = swarms.form;
  const memberKey = auth.member?.email ?? "unknown-member";

  useEffect(() => {
    if (organizationId === undefined) return;
    if (mode === "create") {
      form.beginCreate({ memberKey, organizationId });
      swarms.clearSelected();
    } else if (swarmId !== undefined) {
      void form.beginEdit({ memberKey, organizationId, swarmId });
      void swarms.loadSelected(organizationId, swarmId);
    }
    return () => {
      swarms.clearSelected();
    };
  }, [form, memberKey, mode, organizationId, swarmId, swarms]);

  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;
  const collectionPath = `/org/${activeOrganizationId}/swarms`;
  const formContext = {
    memberKey,
    mode,
    organizationId: activeOrganizationId,
    swarmId: mode === "edit" ? (swarmId ?? null) : null,
  };
  const contextReady = form.isActiveFor(formContext);
  const editUnavailable =
    contextReady &&
    mode === "edit" &&
    !form.isLoading &&
    form.serverSwarm === null;
  const selectedSwarm =
    swarms.selectedSwarm?.id === swarmId ? swarms.selectedSwarm : null;

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    const saved = await form.submit();
    if (saved === null) return;
    swarms.acceptSwarm(saved);
    if (mode === "create") {
      void navigate(`${collectionPath}/${saved.id}/edit`, { replace: true });
    }
  }

  function setField<Field extends keyof SwarmFormValues>(
    field: Field,
    value: SwarmFormValues[Field],
  ): void {
    form.setField(field, value);
  }

  return (
    <section
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
      aria-labelledby="swarm-form-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <Button
            className="-ml-3"
            variant="ghost"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Swarms
          </Button>
          <div>
            <h1
              id="swarm-form-title"
              className="text-2xl font-semibold tracking-tight"
            >
              {mode === "create" ? "New Swarm" : "Edit Swarm"}
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              {mode === "create"
                ? "Name the Swarm first. You can add Agents and publish its topology next."
                : "Maintain the draft topology, then publish one immutable revision for new work."}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {form.hasLocalDraft ? (
            <span className="text-xs text-muted-foreground">
              Draft saved locally {formatSwarmDate(form.savedAt).label}
            </span>
          ) : null}
          <Button
            variant="outline"
            disabled={!contextReady || form.isLoading || editUnavailable}
            onClick={() =>
              mode === "create"
                ? form.startNew({
                    memberKey,
                    organizationId: activeOrganizationId,
                  })
                : form.discardLocalDraft()
            }
          >
            <RotateCcw aria-hidden="true" />
            {mode === "create" ? "Start new" : "Discard draft"}
          </Button>
        </div>
      </header>

      {!contextReady || form.isLoading ? (
        <FormSkeleton />
      ) : editUnavailable ? (
        <div className="space-y-4 border border-destructive/30 bg-destructive/5 p-4 sm:p-5">
          <p className="text-sm text-destructive" role="alert">
            {form.errorMessage ??
              "This Swarm could not be loaded. It may no longer exist."}
          </p>
          <Button
            variant="outline"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Back to Swarms
          </Button>
        </div>
      ) : (
        <>
          <form className="space-y-6" onSubmit={(event) => void submit(event)}>
            <section className="grid gap-5 border p-4 sm:p-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
              <div>
                <h2 className="text-base font-medium">Identity</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  A stable organization-owned identity for this coordinated
                  Agent topology.
                </p>
              </div>
              <div className="min-w-0 space-y-5">
                <FormField
                  error={form.fieldErrors.name}
                  htmlFor="swarm-name"
                  label="Name"
                  required
                >
                  <Input
                    id="swarm-name"
                    maxLength={100}
                    value={form.values.name}
                    aria-invalid={form.fieldErrors.name !== undefined}
                    onChange={(event) => setField("name", event.target.value)}
                  />
                </FormField>
                <FormField
                  error={form.fieldErrors.description}
                  htmlFor="swarm-description"
                  label="Description"
                  description="Explain the shared purpose of this Swarm. Agent-specific roles are configured below."
                >
                  <Textarea
                    id="swarm-description"
                    maxLength={2_000}
                    rows={6}
                    value={form.values.description}
                    aria-invalid={form.fieldErrors.description !== undefined}
                    onChange={(event) =>
                      setField("description", event.target.value)
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    {form.values.description.length.toLocaleString()} / 2,000
                  </p>
                </FormField>
              </div>
            </section>
            {form.errorMessage !== null ? (
              <div
                className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                role="alert"
              >
                {form.errorMessage}
              </div>
            ) : null}
            {form.successMessage !== null ? (
              <div className="border p-3 text-sm" role="status">
                {form.successMessage}
              </div>
            ) : null}
            {form.draftStorageErrorMessage !== null ? (
              <div className="border p-3 text-sm" role="alert">
                {form.draftStorageErrorMessage}
              </div>
            ) : null}
            <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                disabled={form.isSubmitting}
                onClick={() => void navigate(collectionPath)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={form.isSubmitting || !form.isDirty}
              >
                {form.isSubmitting
                  ? "Saving…"
                  : mode === "create"
                    ? "Create Swarm"
                    : "Save details"}
              </Button>
            </div>
          </form>

          {mode === "edit" && swarms.selectedErrorMessage !== null ? (
            <div className="space-y-3 border border-destructive/30 bg-destructive/5 p-4 sm:p-5">
              <p className="text-sm text-destructive" role="alert">
                {swarms.selectedErrorMessage}
              </p>
              <Button
                type="button"
                variant="outline"
                disabled={swarms.isSelectedLoading}
                onClick={() =>
                  void swarms.loadSelected(activeOrganizationId, swarmId ?? "")
                }
              >
                {swarms.isSelectedLoading ? "Retrying…" : "Retry topology"}
              </Button>
            </div>
          ) : mode === "edit" && selectedSwarm !== null ? (
            <>
              {swarms.actionErrorMessage !== null ? (
                <div
                  className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                  role="alert"
                >
                  {swarms.actionErrorMessage}
                </div>
              ) : null}
              {swarms.actionSuccessMessage !== null ? (
                <div className="border p-3 text-sm" role="status">
                  {swarms.actionSuccessMessage}
                </div>
              ) : null}
              <SwarmMembersSection
                actionErrorMessage={swarms.actionErrorMessage}
                activeAction={swarms.activeAction}
                availableAgents={swarms.availableAgents}
                isLoading={swarms.isSelectedLoading}
                members={swarms.selectedMemberViews}
                onAdd={(agentId, description) =>
                  swarms.addMember(activeOrganizationId, agentId, description)
                }
                onEnsureAgents={() => {
                  if (swarms.availableAgents.length === 0)
                    void swarms.loadAvailableAgents(activeOrganizationId);
                }}
                onRemove={(agentId) =>
                  swarms.removeMember(activeOrganizationId, agentId)
                }
              />
              <SwarmLifecycleSection
                activeAction={swarms.activeAction}
                hasUnsavedDetails={form.isDirty}
                members={swarms.selectedMemberViews}
                swarm={selectedSwarm}
                onPublish={() => swarms.publish(activeOrganizationId)}
                onRevoke={(reason) =>
                  swarms.revoke(activeOrganizationId, reason)
                }
                onWithdraw={() => swarms.withdraw(activeOrganizationId)}
              />
            </>
          ) : mode === "edit" ? (
            <FormSkeleton />
          ) : null}
        </>
      )}
    </section>
  );
});

function FormField({
  children,
  description,
  error,
  htmlFor,
  label,
  required,
}: {
  children: React.ReactNode;
  description?: string;
  error?: string;
  htmlFor: string;
  label: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </Label>
      {description !== undefined ? (
        <p className="text-xs leading-5 text-muted-foreground">{description}</p>
      ) : null}
      {children}
      {error !== undefined ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function FormSkeleton() {
  return (
    <div className="grid gap-5 border p-4 sm:p-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <div className="space-y-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-4 w-full" />
      </div>
      <div className="space-y-5">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}

export { SwarmFormPage };
