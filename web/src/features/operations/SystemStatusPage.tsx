import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  ServerCog,
} from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, type ReactNode } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatOperationDate,
  formatOperationEnum,
} from "@/features/operations/operation-formatters";
import type {
  EventHealth,
  ServiceHealth,
} from "@/features/operations/operations.types";

const SystemStatusPage = observer(function SystemStatusPage() {
  const { operations } = useRootStore();
  const store = operations.health;

  useEffect(() => {
    void store.load("system");
  }, [store]);

  function refresh(): void {
    void store.load("system");
  }

  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="system-status-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="system-status-title"
            className="text-2xl font-semibold tracking-tight"
          >
            System status
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            A current operational snapshot of the API and event-processing
            boundary. Provider verification remains on each provider
            configuration.
          </p>
        </div>
        <Button variant="outline" disabled={store.isLoading} onClick={refresh}>
          <RefreshCw
            className={store.isLoading ? "animate-spin" : undefined}
            aria-hidden="true"
          />
          Refresh
        </Button>
      </header>

      {store.errorMessage === null ? null : (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {store.errorMessage}
        </div>
      )}

      {store.serviceHealth === null && store.isLoading ? (
        <StatusSkeleton />
      ) : store.serviceHealth === null || store.eventHealth === null ? (
        <div className="border py-16 text-center">
          <ServerCog
            className="mx-auto size-5 text-muted-foreground"
            aria-hidden="true"
          />
          <p className="mt-3 text-sm font-medium">
            System status has not been checked
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Run both health checks to see a current snapshot.
          </p>
          <Button className="mt-4" variant="outline" onClick={refresh}>
            Check system
          </Button>
        </div>
      ) : (
        <SystemSnapshot
          events={store.eventHealth}
          service={store.serviceHealth}
        />
      )}
    </section>
  );
});

function SystemSnapshot({
  events,
  service,
}: {
  events: EventHealth;
  service: ServiceHealth;
}) {
  const eventDanger =
    events.durable.dead_letter_count > 0 ||
    events.durable.unsupported_delivery_count > 0 ||
    !events.local.healthy;
  const checked = formatOperationDate(service.checkedAt);
  const observed = formatOperationDate(events.durable.observed_at);

  return (
    <div className="space-y-8">
      <section className="grid gap-px border bg-border sm:grid-cols-2 xl:grid-cols-3">
        <StatusCard
          detail={`${service.latencyMs} ms · ${checked.label}`}
          healthy={service.online}
          label="API"
        />
        <StatusCard
          detail={`${events.local.handler_count} handlers · ${formatOperationEnum(events.local.process_role)}`}
          healthy={events.local.healthy}
          label="Local listeners"
        />
        <StatusCard
          detail={`${events.durable.pending_count} pending · ${events.durable.dead_letter_count} dead letter`}
          healthy={!eventDanger}
          label="Durable delivery"
        />
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="font-medium">Current snapshot</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Operational facts returned by the running API process.
          </p>
        </div>
        <dl className="divide-y border-y">
          <DetailRow label="API latency">
            {service.latencyMs.toLocaleString()} ms
          </DetailRow>
          <DetailRow label="API checked">
            <time dateTime={service.checkedAt} title={checked.title}>
              {checked.label}
            </time>
          </DetailRow>
          <DetailRow label="Events observed">
            <time dateTime={events.durable.observed_at} title={observed.title}>
              {observed.label}
            </time>
          </DetailRow>
          <DetailRow label="Durable deliveries">
            {events.durable.total_count.toLocaleString()}
          </DetailRow>
          <DetailRow label="Pending / running">
            {events.durable.pending_count.toLocaleString()} /{" "}
            {events.durable.running_count.toLocaleString()}
          </DetailRow>
          <DetailRow label="Dead letter">
            {events.durable.dead_letter_count > 0 ? (
              <Badge variant="destructive">
                {events.durable.dead_letter_count}
              </Badge>
            ) : (
              "0"
            )}
          </DetailRow>
          <DetailRow label="Unsupported">
            {events.durable.unsupported_delivery_count > 0 ? (
              <Badge variant="destructive">
                {events.durable.unsupported_delivery_count}
              </Badge>
            ) : (
              "0"
            )}
          </DetailRow>
        </dl>
      </section>

      <p className="border-l-2 pl-3 text-sm leading-6 text-muted-foreground">
        This surface does not invent an aggregate platform status. Each row
        reports a concrete health endpoint or queue fact; socket/provider
        readiness remains separately verifiable.
      </p>
    </div>
  );
}

function StatusCard({
  detail,
  healthy,
  label,
}: {
  detail: string;
  healthy: boolean;
  label: string;
}) {
  return (
    <article className="bg-background p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-medium">{label}</h2>
        <Badge variant={healthy ? "outline" : "destructive"}>
          {healthy ? (
            <CheckCircle2 aria-hidden="true" />
          ) : (
            <AlertTriangle aria-hidden="true" />
          )}
          {healthy ? "Operational" : "Needs attention"}
        </Badge>
      </div>
      <p className="mt-3 break-words text-sm text-muted-foreground">{detail}</p>
    </article>
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
    <div className="grid gap-1 py-3 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}

function StatusSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }, (_, index) => (
          <Skeleton className="h-28" key={index} />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export { SystemStatusPage };
