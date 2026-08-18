import { AlertTriangle, CheckCircle2, Clock3, RefreshCw } from "lucide-react";
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
import type { EventHealth } from "@/features/operations/operations.types";

const EventHealthPage = observer(function EventHealthPage() {
  const { operations } = useRootStore();
  const store = operations.health;

  useEffect(() => {
    void store.load("events");
  }, [store]);

  function refresh(): void {
    void store.load("events");
  }

  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="event-health-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="event-health-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Event health
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Delivery health for auditable durable events plus the local
            in-process listener manifest. Event payloads remain in their owning
            modules.
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

      {store.eventHealth === null && store.isLoading ? (
        <HealthSkeleton />
      ) : store.eventHealth === null ? (
        <EmptyHealth onLoad={refresh} />
      ) : (
        <EventHealthDetails health={store.eventHealth} />
      )}
    </section>
  );
});

function EventHealthDetails({ health }: { health: EventHealth }) {
  const observed = formatOperationDate(health.durable.observed_at);
  const hasDeliveryDanger =
    health.durable.dead_letter_count > 0 ||
    health.durable.unsupported_delivery_count > 0;

  return (
    <div className="space-y-8">
      <section className="space-y-3" aria-labelledby="delivery-summary-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="delivery-summary-title" className="font-medium">
              Durable delivery
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Organization-scoped counts observed by the API.
            </p>
          </div>
          <Badge variant={hasDeliveryDanger ? "destructive" : "outline"}>
            {hasDeliveryDanger ? (
              <AlertTriangle aria-hidden="true" />
            ) : (
              <CheckCircle2 aria-hidden="true" />
            )}
            {hasDeliveryDanger ? "Needs attention" : "Healthy"}
          </Badge>
        </div>
        <div className="grid gap-px border bg-border sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Pending" value={health.durable.pending_count} />
          <Metric label="Running" value={health.durable.running_count} />
          <Metric label="Succeeded" value={health.durable.succeeded_count} />
          <Metric
            danger={health.durable.dead_letter_count > 0}
            label="Dead letter"
            value={health.durable.dead_letter_count}
          />
        </div>
        <dl className="divide-y border-y">
          <DetailRow label="Total deliveries">
            {health.durable.total_count.toLocaleString()}
          </DetailRow>
          <DetailRow label="Unsupported deliveries">
            <DangerValue value={health.durable.unsupported_delivery_count} />
          </DetailRow>
          <DetailRow label="Oldest pending">
            {formatAge(health.durable.oldest_pending_age_seconds)}
          </DetailRow>
          <DetailRow label="Observed">
            <time dateTime={health.durable.observed_at} title={observed.title}>
              {observed.label}
            </time>
          </DetailRow>
        </dl>
      </section>

      <section className="space-y-3" aria-labelledby="listener-health-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="listener-health-title" className="font-medium">
              Local listeners
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              In-process handlers registered in this API process.
            </p>
          </div>
          <Badge variant={health.local.healthy ? "outline" : "destructive"}>
            {health.local.healthy ? (
              <CheckCircle2 aria-hidden="true" />
            ) : (
              <AlertTriangle aria-hidden="true" />
            )}
            {health.local.healthy ? "Healthy" : "Unhealthy"}
          </Badge>
        </div>
        <dl className="divide-y border-y">
          <DetailRow label="Process role">
            {formatOperationEnum(health.local.process_role)}
          </DetailRow>
          <DetailRow label="Delivery class">
            {formatOperationEnum(health.local.delivery_class)}
          </DetailRow>
          <DetailRow label="Manifest version">
            {health.local.manifest_version}
          </DetailRow>
          <DetailRow label="Handlers">{health.local.handler_count}</DetailRow>
          <DetailRow label="Event types">{health.local.event_count}</DetailRow>
        </dl>
        <IdentifierList
          empty="No local handlers registered"
          items={health.local.handler_ids}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <ConsumerList
          description="Code-owned consumers available for durable delivery."
          empty="No durable consumers registered"
          items={health.durable.registered_consumers.map((consumer) => ({
            detail: `${consumer.event_type} · v${consumer.event_version}`,
            name: consumer.consumer_name,
          }))}
          title="Registered consumers"
        />
        <ConsumerList
          danger
          description="Deliveries whose consumer contract is not registered in this process."
          empty="No unsupported consumers"
          items={health.durable.unsupported_consumers.map((consumer) => ({
            detail: `${consumer.event_type} · v${consumer.event_version} · ${consumer.delivery_count} deliveries`,
            name: consumer.consumer_name,
          }))}
          title="Unsupported consumers"
        />
      </section>
    </div>
  );
}

function Metric({
  danger = false,
  label,
  value,
}: {
  danger?: boolean;
  label: string;
  value: number;
}) {
  return (
    <div className="bg-background p-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className={
          danger
            ? "mt-2 text-2xl font-semibold text-destructive"
            : "mt-2 text-2xl font-semibold"
        }
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}

function DangerValue({ value }: { value: number }) {
  return value > 0 ? (
    <Badge variant="destructive">{value.toLocaleString()}</Badge>
  ) : (
    <span>0</span>
  );
}

function ConsumerList({
  danger = false,
  description,
  empty,
  items,
  title,
}: {
  danger?: boolean;
  description: string;
  empty: string;
  items: readonly { detail: string; name: string }[];
  title: string;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-medium">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      {items.length === 0 ? (
        <div className="border py-8 text-center text-sm text-muted-foreground">
          {empty}
        </div>
      ) : (
        <div className="divide-y border">
          {items.map((item) => (
            <article
              className="min-w-0 p-3"
              key={`${item.name}:${item.detail}`}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="break-all text-sm font-medium">{item.name}</p>
                {danger ? (
                  <Badge variant="destructive">Unsupported</Badge>
                ) : null}
              </div>
              <p className="mt-1 break-all text-xs text-muted-foreground">
                {item.detail}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function IdentifierList({
  empty,
  items,
}: {
  empty: string;
  items: readonly string[];
}) {
  if (items.length === 0)
    return (
      <div className="border py-8 text-center text-sm text-muted-foreground">
        {empty}
      </div>
    );
  return (
    <div className="divide-y border">
      {items.map((item) => (
        <p className="break-all p-3 font-mono text-xs" key={item}>
          {item}
        </p>
      ))}
    </div>
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

function formatAge(seconds: number | null): string {
  if (seconds === null) return "No pending deliveries";
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hr ${minutes % 60} min`;
}

function HealthSkeleton() {
  return (
    <div className="space-y-6">
      {Array.from({ length: 3 }, (_, index) => (
        <Skeleton className="h-40 w-full" key={index} />
      ))}
    </div>
  );
}

function EmptyHealth({ onLoad }: { onLoad: () => void }) {
  return (
    <div className="border py-16 text-center">
      <Clock3
        className="mx-auto size-5 text-muted-foreground"
        aria-hidden="true"
      />
      <p className="mt-3 text-sm font-medium">
        Event health has not been checked
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Run a current health check against the platform.
      </p>
      <Button className="mt-4" variant="outline" onClick={onLoad}>
        Check event health
      </Button>
    </div>
  );
}

export { EventHealthPage };
