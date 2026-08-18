import { Pencil, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import type { ReactNode } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import { MemoryReindexPanel } from "@/features/memory/MemoryReindexPanel";
import { ProviderConfigActions } from "@/features/providers/ProviderConfigActions";
import { ProviderStatusBadge } from "@/features/providers/ProviderStatusBadge";
import {
  formatProviderDate,
  formatProviderFieldValue,
  formatProviderIdentifier,
} from "@/features/providers/provider-formatters";
import type {
  ProviderConfigRecord,
  ProviderDefinition,
  ProviderFieldValue,
} from "@/features/providers/providers.types";

interface ProviderDetailsDrawerProps {
  configId: string | undefined;
  onClose: () => void;
  onEdit: (configId: string) => void;
}

const ProviderDetailsDrawer = observer(function ProviderDetailsDrawer({
  configId,
  onClose,
  onEdit,
}: ProviderDetailsDrawerProps) {
  const { providers } = useRootStore();
  const config = providers.selectedConfig;
  const definition =
    config === null
      ? null
      : (providers
          .definitionFor(config.capability)
          ?.providers.find((provider) => provider.id === config.provider) ??
        null);

  return (
    <Drawer
      open={configId !== undefined}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,40rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle>{config?.name ?? "Provider details"}</DrawerTitle>
          <DrawerDescription>
            Saved settings, credential presence, and readiness returned by Eylo.
          </DrawerDescription>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close provider details"
          title="Close"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {providers.isSelectedLoading && config === null ? (
            <ProviderDetailsSkeleton />
          ) : providers.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {providers.selectedErrorMessage}
            </div>
          ) : config !== null ? (
            <ProviderDetails config={config} definition={definition} />
          ) : null}
        </div>

        {config === null ? null : (
          <DrawerFooter className="flex-row border-t p-4">
            <Button className="flex-1" onClick={() => onEdit(config.id)}>
              <Pencil aria-hidden="true" />
              Edit configuration
            </Button>
            <ProviderConfigActions
              config={config}
              onDeleted={onClose}
              onEdit={() => onEdit(config.id)}
            />
          </DrawerFooter>
        )}
      </DrawerContent>
    </Drawer>
  );
});

function ProviderDetails({
  config,
  definition,
}: {
  config: ProviderConfigRecord;
  definition: ProviderDefinition | null;
}) {
  const verifiedAt = formatProviderDate(config.verifiedAt);
  const settingFields = definition?.fields.filter(
    (field) => field.target === "config",
  );
  const secretFields = definition?.fields.filter(
    (field) => field.target === "secrets",
  );

  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Status">
          <ProviderStatusBadge
            configured={config.configured}
            enabled={config.enabled}
            ready={config.ready}
            verified={config.verified}
          />
        </DetailRow>
        <DetailRow label="Provider">
          {definition?.label ?? formatProviderIdentifier(config.provider)}
        </DetailRow>
        <DetailRow label="Revision">{config.revision}</DetailRow>
        <DetailRow label="Verified">
          {verifiedAt.exact === null ? (
            verifiedAt.label
          ) : (
            <time
              dateTime={verifiedAt.exact}
              title={`${verifiedAt.exact} (UTC)`}
            >
              {verifiedAt.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Configuration ID">
          <CodeValue>{config.id}</CodeValue>
        </DetailRow>
      </DetailsSection>

      <DetailsSection title="Settings">
        {(settingFields ?? []).length === 0 ? (
          <DetailRow label="Settings">No non-secret settings</DetailRow>
        ) : (
          settingFields?.map((field) => (
            <DetailRow key={field.key} label={field.label}>
              <span className="break-words">
                {formatProviderFieldValue(
                  toFieldValue(config.config[field.wire_key]),
                )}
              </span>
            </DetailRow>
          ))
        )}
      </DetailsSection>

      <DetailsSection title="Credentials">
        {(secretFields ?? []).length === 0 ? (
          <DetailRow label="Credentials">
            This provider takes no credentials
          </DetailRow>
        ) : (
          secretFields?.map((field) => (
            <DetailRow key={field.key} label={field.label}>
              {hasStoredSecret(config, field.wire_key)
                ? "Stored securely"
                : "Not stored"}
            </DetailRow>
          ))
        )}
      </DetailsSection>

      <CapabilityDetails config={config} />
    </div>
  );
}

function CapabilityDetails({ config }: { config: ProviderConfigRecord }) {
  if (config.capability === "memory") {
    return <MemoryReindexPanel key={config.id} config={config} />;
  }
  if ("operations" in config.raw) {
    return (
      <BooleanProjection
        title="Telephony operations"
        values={config.raw.operations}
      />
    );
  }
  if ("capabilities" in config.raw) {
    return (
      <BooleanProjection
        title="Storage capabilities"
        values={config.raw.capabilities}
      />
    );
  }
  if ("dimensions" in config.raw && config.raw.dimensions !== null) {
    return (
      <DetailsSection title="Embedding verification">
        <DetailRow label="Dimensions">{config.raw.dimensions}</DetailRow>
      </DetailsSection>
    );
  }
  return null;
}

function BooleanProjection({
  title,
  values,
}: {
  title: string;
  values: Record<string, boolean>;
}) {
  return (
    <DetailsSection title={title}>
      {Object.entries(values).map(([key, value]) => (
        <DetailRow key={key} label={formatProviderIdentifier(key)}>
          {value ? "Supported" : "Not supported"}
        </DetailRow>
      ))}
    </DetailsSection>
  );
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
    <div className="grid gap-1 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm leading-5">{children}</dd>
    </div>
  );
}

function CodeValue({ children }: { children: ReactNode }) {
  return (
    <code className="break-all rounded-sm bg-muted px-1 py-0.5 text-xs">
      {children}
    </code>
  );
}

function hasStoredSecret(
  config: ProviderConfigRecord,
  wireKey: string,
): boolean {
  const value = config.secrets[wireKey];
  return typeof value === "string" && value !== "";
}

function toFieldValue(value: unknown): ProviderFieldValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value
    : null;
}

function ProviderDetailsSkeleton() {
  return (
    <div className="space-y-8" aria-label="Loading provider details">
      {[0, 1, 2].map((section) => (
        <div key={section} className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <div className="space-y-px border-y">
            {[0, 1, 2].map((row) => (
              <div key={row} className="grid grid-cols-[11rem_1fr] gap-4 py-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-full" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export { ProviderDetailsDrawer };
