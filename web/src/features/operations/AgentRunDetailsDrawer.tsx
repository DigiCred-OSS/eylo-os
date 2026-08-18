import { Ban, MessageSquareReply, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";

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
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  formatDuration,
  formatOperationDate,
  formatOperationEnum,
} from "@/features/operations/operation-formatters";
import type {
  AgentInputRequest,
  AgentRun,
} from "@/features/operations/operations.types";

interface AgentRunDetailsDrawerProps {
  onClose: () => void;
  organizationId: string;
  runId: string | undefined;
}

const CANCELLABLE = new Set([
  "queued",
  "running",
  "waiting_for_input",
  "waiting_for_approval",
]);

const AgentRunDetailsDrawer = observer(function AgentRunDetailsDrawer({
  onClose,
  organizationId,
  runId,
}: AgentRunDetailsDrawerProps) {
  const { operations } = useRootStore();
  const store = operations.agentRuns;
  const run = store.selectedRun;
  const [cancelOpen, setCancelOpen] = useState(false);
  const [inputRequest, setInputRequest] = useState<AgentInputRequest | null>(
    null,
  );
  const [response, setResponse] = useState("");
  async function answer(): Promise<void> {
    if (inputRequest === null || response.trim() === "") return;
    const value = parseResponse(response);
    if (await store.answer(organizationId, inputRequest, value)) {
      setInputRequest(null);
      setResponse("");
    }
  }
  return (
    <>
      <Drawer
        open={runId !== undefined}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
        swipeDirection="right"
      >
        <DrawerContent className="[--drawer-content-width:min(100%,52rem)]">
          <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
            <DrawerTitle>
              {run === null ? "Agent run" : `Run …${run.id.slice(-12)}`}
            </DrawerTitle>
            <DrawerDescription>
              Goal, exact Agent revision, workflow evidence, input requests, and
              budget reservation.
            </DrawerDescription>
          </DrawerHeader>
          <Button
            className="absolute top-4 right-4 z-20"
            variant="ghost"
            size="icon"
            aria-label="Close Agent run"
            title="Close"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </Button>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {store.isSelectedLoading && run === null ? (
              <DetailsSkeleton />
            ) : store.selectedErrorMessage !== null ? (
              <ErrorBox>{store.selectedErrorMessage}</ErrorBox>
            ) : run !== null ? (
              <RunDetails
                organizationId={organizationId}
                run={run}
                agentName={operations.agentName(run.agent_id)}
                onAnswer={setInputRequest}
              />
            ) : null}
            {store.actionErrorMessage === null ? null : (
              <div className="mt-4">
                <ErrorBox>{store.actionErrorMessage}</ErrorBox>
              </div>
            )}
          </div>
          {run !== null && CANCELLABLE.has(run.lifecycle) ? (
            <DrawerFooter className="flex-row border-t p-4">
              <Button
                variant="destructive"
                disabled={store.isActing}
                onClick={() => setCancelOpen(true)}
              >
                <Ban aria-hidden="true" />
                Cancel run
              </Button>
            </DrawerFooter>
          ) : null}
        </DrawerContent>
      </Drawer>
      <Dialog
        open={cancelOpen}
        onOpenChange={(open) => {
          if (!store.isActing) setCancelOpen(open);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Cancel this Agent run?</DialogTitle>
            <DialogDescription>
              The cancellation request is durable. Active provider or sandbox
              work is stopped by the worker; completed evidence remains.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={store.isActing}
              onClick={() => setCancelOpen(false)}
            >
              Keep running
            </Button>
            <Button
              variant="destructive"
              disabled={store.isActing}
              onClick={() =>
                void store.cancel(organizationId).then((done) => {
                  if (done) setCancelOpen(false);
                })
              }
            >
              {store.isActing ? "Cancelling…" : "Cancel run"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={inputRequest !== null}
        onOpenChange={(open) => {
          if (!open && !store.isActing) {
            setInputRequest(null);
            setResponse("");
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Respond to Agent</DialogTitle>
            <DialogDescription>{inputRequest?.prompt}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="agent-run-response">Response</Label>
            <Textarea
              id="agent-run-response"
              className="min-h-28"
              value={response}
              onChange={(event) => setResponse(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Plain text is submitted as a string. Valid JSON is submitted as
              its JSON value.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={store.isActing}
              onClick={() => setInputRequest(null)}
            >
              Cancel
            </Button>
            <Button
              disabled={store.isActing || response.trim() === ""}
              onClick={() => void answer()}
            >
              {store.isActing ? "Submitting…" : "Submit response"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

function RunDetails({
  agentName,
  onAnswer,
  organizationId,
  run,
}: {
  agentName: string;
  onAnswer: (request: AgentInputRequest) => void;
  organizationId: string;
  run: AgentRun;
}) {
  const created = formatOperationDate(run.created_at);
  const started = formatOperationDate(run.started_at);
  const finished = formatOperationDate(run.finished_at);
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{formatOperationEnum(run.lifecycle)}</Badge>
          {run.outcome === null ? null : (
            <Badge variant="outline">{formatOperationEnum(run.outcome)}</Badge>
          )}
        </div>
        <p className="break-words text-lg font-medium leading-7">{run.goal}</p>
        {run.failure_summary === null ? null : (
          <ErrorBox>{run.failure_summary}</ErrorBox>
        )}
      </section>
      <DetailsSection title="Authority">
        <DetailRow label="Agent">
          <Link
            className="underline underline-offset-4"
            to={`/org/${organizationId}/agents/${run.agent_id}`}
          >
            {agentName} · revision {run.agent_revision}
          </Link>
        </DetailRow>
        <DetailRow label="Origin">
          <Badge variant="outline">
            {formatOperationEnum(run.origin_kind)}
          </Badge>
        </DetailRow>
        <DetailRow label="Initiated by">
          {formatOperationEnum(run.initiating_principal_kind)} ·{" "}
          <code className="break-all text-xs">
            {run.initiating_principal_id}
          </code>
        </DetailRow>
        <DetailRow label="State revision">{run.state_revision}</DetailRow>
      </DetailsSection>
      <DetailsSection title="Timing">
        <DetailRow label="Created">
          <time dateTime={run.created_at} title={created.title}>
            {created.label}
          </time>
        </DetailRow>
        <DetailRow label="Started">
          {run.started_at === null ? (
            started.label
          ) : (
            <time dateTime={run.started_at} title={started.title}>
              {started.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Finished">
          {run.finished_at === null ? (
            finished.label
          ) : (
            <time dateTime={run.finished_at} title={finished.title}>
              {finished.label}
            </time>
          )}
        </DetailRow>
      </DetailsSection>
      {run.reservation === null ? null : (
        <DetailsSection title="Execution budget">
          <DetailRow label="Tokens">
            {run.reservation.used_tokens.toLocaleString()} /{" "}
            {run.reservation.token_limit.toLocaleString()}
          </DetailRow>
          <DetailRow label="Active time">
            {formatDuration(run.reservation.active_milliseconds)} /{" "}
            {formatDuration(run.reservation.time_limit_milliseconds)}
          </DetailRow>
          <DetailRow label="Cost">
            {run.reservation.used_cost_microunits.toLocaleString()} /{" "}
            {run.reservation.cost_limit_microunits.toLocaleString()} microunits
          </DetailRow>
          <DetailRow label="Capacity">
            {run.reservation.active ? "Reserved" : "Released"}
          </DetailRow>
        </DetailsSection>
      )}
      <section className="space-y-3">
        <div>
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Input requests
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Questions the run could not resolve without a member.
          </p>
        </div>
        {run.input_requests.length === 0 ? (
          <div className="border py-8 text-center text-sm text-muted-foreground">
            No input requests
          </div>
        ) : (
          <div className="divide-y border">
            {run.input_requests.map((request) => (
              <article className="space-y-2 p-3" key={request.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{request.prompt}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatOperationEnum(request.kind)}
                    </p>
                  </div>
                  <Badge variant="outline">
                    {formatOperationEnum(request.status)}
                  </Badge>
                </div>
                {request.status === "pending" ? (
                  <Button size="sm" onClick={() => onAnswer(request)}>
                    <MessageSquareReply aria-hidden="true" />
                    Respond
                  </Button>
                ) : request.response === null ? null : (
                  <pre className="whitespace-pre-wrap break-words bg-muted p-2 text-xs">
                    {JSON.stringify(request.response, null, 2)}
                  </pre>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="space-y-3">
        <div>
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Workflow steps
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Product-safe summaries and evidence in execution order.
          </p>
        </div>
        {run.steps.length === 0 ? (
          <div className="border py-8 text-center text-sm text-muted-foreground">
            No steps recorded
          </div>
        ) : (
          <div className="divide-y border">
            {run.steps.map((step) => (
              <article className="space-y-2 p-3" key={step.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    {step.safe_summary ?? formatOperationEnum(step.kind)}
                  </p>
                  <Badge variant="outline">
                    {formatOperationEnum(step.status)}
                  </Badge>
                </div>
                <p className="break-all text-xs text-muted-foreground">
                  {step.step_key}
                </p>
                {step.evidence === null ? null : (
                  <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words bg-muted p-2 text-xs">
                    {JSON.stringify(step.evidence, null, 2)}
                  </pre>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      {run.result === null ? null : (
        <DetailsSection title="Result">
          <pre className="overflow-auto whitespace-pre-wrap break-words py-3 text-xs">
            {JSON.stringify(run.result, null, 2)}
          </pre>
        </DetailsSection>
      )}
    </div>
  );
}

function parseResponse(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}
function DetailsSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h2>
      <dl className="divide-y border-y">{children}</dl>
    </section>
  );
}
function DetailRow({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}
function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div
      className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
      role="alert"
    >
      {children}
    </div>
  );
}
function DetailsSkeleton() {
  return (
    <div className="space-y-5">
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  );
}

export { AgentRunDetailsDrawer };
