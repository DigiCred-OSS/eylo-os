import { Pencil, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import type { ReactNode } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
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
import { formatVoiceDate } from "@/features/voice/voice-formatters";
import { voiceRuntimeMode } from "@/features/voice/voice.query";
import type {
  VoiceConfigCompatibility,
  VoiceConfigRecord,
} from "@/features/voice/voice.types";

const VoiceConfigDetailsDrawer = observer(function VoiceConfigDetailsDrawer({
  onClose,
  onEdit,
  voiceConfigId,
}: {
  onClose: () => void;
  onEdit: (voiceConfigId: string) => void;
  voiceConfigId: string | undefined;
}) {
  const { voice } = useRootStore();
  const voiceConfig = voice.selectedVoiceConfig;
  return (
    <Drawer
      open={voiceConfigId !== undefined}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,48rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle>
            {voiceConfig?.name ?? "Voice Config details"}
          </DrawerTitle>
          <DrawerDescription>
            Runtime authority, Eylo-owned behavior, and provider-native support.
          </DrawerDescription>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close Voice Config details"
          title="Close"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {voice.isSelectedLoading && voiceConfig === null ? (
            <VoiceDetailsSkeleton />
          ) : voice.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {voice.selectedErrorMessage}
            </div>
          ) : voiceConfig === null ? null : (
            <VoiceConfigDetails
              compatibility={voice.selectedCompatibility}
              compatibilityError={voice.compatibilityErrorMessage}
              compatibilityLoading={voice.isCompatibilityLoading}
              voiceConfig={voiceConfig}
            />
          )}
        </div>

        {voiceConfig === null ? null : (
          <DrawerFooter className="border-t p-4">
            <Button className="w-full" onClick={() => onEdit(voiceConfig.id)}>
              <Pencil aria-hidden="true" />
              Edit Voice Config
            </Button>
          </DrawerFooter>
        )}
      </DrawerContent>
    </Drawer>
  );
});

function VoiceConfigDetails({
  compatibility,
  compatibilityError,
  compatibilityLoading,
  voiceConfig,
}: {
  compatibility: VoiceConfigCompatibility | null;
  compatibilityError: string | null;
  compatibilityLoading: boolean;
  voiceConfig: VoiceConfigRecord;
}) {
  const createdAt = formatVoiceDate(voiceConfig.created_at);
  const updatedAt = formatVoiceDate(voiceConfig.updated_at);
  const config = voiceConfig.config;
  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Runtime">
          <Badge variant="outline">
            {voiceRuntimeMode(voiceConfig) === "realtime"
              ? "Realtime"
              : "Decomposed"}
          </Badge>
        </DetailRow>
        <DetailRow label="Revision">{voiceConfig.revision}</DetailRow>
        <DetailRow label="Description">
          <LongValue>{voiceConfig.description ?? "No description"}</LongValue>
        </DetailRow>
        <DetailRow label="STT config">
          <CodeValue>
            {config.stt_provider_config_id ?? "Not selected"}
          </CodeValue>
        </DetailRow>
        <DetailRow label="TTS config">
          <CodeValue>
            {config.tts_provider_config_id ?? "Not selected"}
          </CodeValue>
        </DetailRow>
        <DetailRow label="Realtime config">
          <CodeValue>
            {config.realtime_provider_config_id ?? "Not selected"}
          </CodeValue>
        </DetailRow>
        <DetailRow label="Recording storage">
          <CodeValue>
            {config.storage_provider_config_id ?? "Not selected"}
          </CodeValue>
        </DetailRow>
      </DetailsSection>

      <DetailsSection title="Eylo platform features">
        {compatibilityLoading && compatibility === null ? (
          <CapabilitySkeleton />
        ) : compatibilityError !== null ? (
          <div className="py-3 text-sm text-destructive" role="alert">
            {compatibilityError}
          </div>
        ) : compatibility === null ? null : (
          compatibility.platform_features.map((feature) => (
            <DetailRow key={feature.key} label={feature.label}>
              <div className="space-y-1">
                <Badge variant="outline">
                  {feature.enabled ? "Enabled" : "Not enabled"}
                </Badge>
                <p className="text-xs leading-5 text-muted-foreground">
                  {feature.description}
                </p>
              </div>
            </DetailRow>
          ))
        )}
      </DetailsSection>

      <section className="space-y-4">
        <div>
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Provider-native capabilities
          </h2>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">
            These describe vendor support only. False or absent native support
            does not remove the Eylo platform features above.
          </p>
        </div>
        {compatibilityLoading && compatibility === null ? (
          <CapabilitySkeleton />
        ) : compatibilityError !== null ? (
          <div className="border border-destructive/30 p-3 text-sm text-destructive">
            {compatibilityError}
          </div>
        ) : compatibility?.selected_providers.length === 0 ? (
          <div className="border p-4 text-sm text-muted-foreground">
            No voice providers are selected yet.
          </div>
        ) : (
          compatibility?.selected_providers.map((provider) => (
            <section
              key={`${provider.kind}:${provider.provider_config_id}`}
              className="border"
            >
              <header className="flex flex-wrap items-center justify-between gap-2 border-b p-3">
                <div>
                  <p className="text-sm font-medium">
                    {formatIdentifier(provider.provider)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {provider.kind.toUpperCase()}
                  </p>
                </div>
                <Badge variant="outline">
                  {provider.ready ? "Ready" : "Not ready"}
                </Badge>
              </header>
              <dl className="divide-y px-3">
                {Object.entries(provider.native_capabilities).map(
                  ([key, value]) => (
                    <DetailRow key={key} label={formatIdentifier(key)}>
                      {typeof value === "boolean" ? (
                        <Badge variant="outline">
                          {value ? "Supported" : "Not supported"}
                        </Badge>
                      ) : (
                        <LongValue>{formatCapabilityValue(value)}</LongValue>
                      )}
                    </DetailRow>
                  ),
                )}
              </dl>
            </section>
          ))
        )}
        {compatibility === null ? null : (
          <p className="border bg-muted/20 p-3 text-sm leading-5 text-muted-foreground">
            {compatibility.guidance}
          </p>
        )}
      </section>

      <DetailsSection title="Record">
        <DetailRow label="Created">
          <DateValue value={createdAt} />
        </DetailRow>
        <DetailRow label="Updated">
          <DateValue value={updatedAt} />
        </DetailRow>
        <DetailRow label="Voice Config ID">
          <CodeValue>{voiceConfig.id}</CodeValue>
        </DetailRow>
      </DetailsSection>
    </div>
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
    <div className="grid gap-1 py-3 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
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

function LongValue({ children }: { children: ReactNode }) {
  return <span className="break-words">{children}</span>;
}

function DateValue({
  value,
}: {
  value: { exact: string | null; label: string };
}) {
  return value.exact === null ? (
    value.label
  ) : (
    <time dateTime={value.exact} title={`${value.exact} (UTC)`}>
      {value.label}
    </time>
  );
}

function formatIdentifier(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/gu, (character) => character.toUpperCase());
}

function formatCapabilityValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (value === null || value === undefined) {
    return "Not reported";
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function CapabilitySkeleton() {
  return (
    <div className="space-y-3 py-3">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

function VoiceDetailsSkeleton() {
  return (
    <div className="space-y-8" aria-label="Loading Voice Config details">
      {[0, 1, 2].map((section) => (
        <div key={section} className="space-y-3">
          <Skeleton className="h-3 w-32" />
          <div className="space-y-3 border-y py-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

export { VoiceConfigDetailsDrawer };
