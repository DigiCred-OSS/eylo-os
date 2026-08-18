import { Check, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

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
import type { ProviderReferencesStore } from "@/features/providers/provider-references.store";
import {
  providerCollectionPath,
  withReturnContext,
} from "@/features/providers/provider-navigation";
import type {
  ProviderCapability,
  ProviderReferenceField,
} from "@/features/providers/providers.types";
import { cn } from "@/lib/utils";

interface ProviderConfigReferenceFieldProps {
  description: string;
  field: ProviderReferenceField;
  label: string;
  onChange: (value: string | null) => void;
  organizationId: string;
  references: ProviderReferencesStore;
  value: string | null;
}

const ProviderConfigReferenceField = observer(
  function ProviderConfigReferenceField({
    description,
    field,
    label,
    onChange,
    organizationId,
    references,
    value,
  }: ProviderConfigReferenceFieldProps) {
    const location = useLocation();
    const navigate = useNavigate();
    const [isOpen, setIsOpen] = useState(false);
    const [search, setSearch] = useState("");
    const selectedOption = references.getOption(field, value);
    const fieldOptions = references.options[field];
    const options = useMemo(() => {
      const normalizedSearch = search.trim().toLowerCase();
      return normalizedSearch === ""
        ? fieldOptions
        : fieldOptions.filter((option) =>
            `${option.label} ${option.description}`
              .toLowerCase()
              .includes(normalizedSearch),
          );
    }, [fieldOptions, search]);
    const isLoading = references.loadingFields.has(field);
    const hasError = references.errorFields.has(field);
    const providerCapability = providerCapabilityFor(field);
    const configurePath = withReturnContext(
      providerCollectionPath(organizationId, providerCapability),
      `${location.pathname}${location.search}`,
    );
    const needsConfiguration =
      !fieldOptions.some((option) => option.isSelectable) ||
      (value !== null && selectedOption?.isSelectable !== true);

    function setOpen(open: boolean): void {
      setIsOpen(open);
      if (open) {
        setSearch("");
        void references.load(field, organizationId, true);
      }
    }

    function configureProvider(): void {
      setIsOpen(false);
      void navigate(configurePath);
    }

    return (
      <div className="flex flex-col gap-4 border p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium">{label}</p>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">
            {description}
          </p>
          <p className="mt-2 break-words text-xs text-muted-foreground">
            {value === null
              ? "Not configured"
              : selectedOption === null
                ? `Selected: ${value}`
                : `${selectedOption.label} · ${selectedOption.status}`}
          </p>
          {needsConfiguration ? (
            <Button
              className="mt-2 h-auto px-0 py-0 text-xs"
              type="button"
              variant="link"
              onClick={configureProvider}
            >
              Configure {providerCapabilityLabel(providerCapability)}
            </Button>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {value !== null ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => onChange(null)}
            >
              Clear
            </Button>
          ) : null}
          <Button type="button" variant="outline" onClick={() => setOpen(true)}>
            {value === null ? "Choose" : "Change"}
          </Button>
        </div>

        <Dialog open={isOpen} onOpenChange={setOpen}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader className="pr-8">
              <DialogTitle>Choose {label.toLowerCase()}</DialogTitle>
              <DialogDescription>
                Only ready configurations can be assigned. Eylo does not choose
                a default.
              </DialogDescription>
            </DialogHeader>

            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                className="pl-9"
                aria-label={`Search ${label}`}
                placeholder="Search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>

            <div className="max-h-80 min-h-36 overflow-y-auto border">
              {isLoading ? (
                <p className="p-6 text-center text-sm text-muted-foreground">
                  Loading options…
                </p>
              ) : hasError ? (
                <div className="p-6 text-center">
                  <p className="text-sm text-destructive">
                    Options could not be loaded.
                  </p>
                  <Button
                    className="mt-3"
                    type="button"
                    variant="outline"
                    onClick={() =>
                      void references.load(field, organizationId, true)
                    }
                  >
                    Try again
                  </Button>
                </div>
              ) : options.length === 0 ? (
                <p className="p-6 text-center text-sm text-muted-foreground">
                  {fieldOptions.length === 0
                    ? "No options are available."
                    : "No options match this search."}
                </p>
              ) : (
                <div className="divide-y">
                  {options.map((option) => {
                    const isSelected = option.id === value;
                    return (
                      <button
                        key={option.id}
                        className={cn(
                          "grid w-full grid-cols-[1fr_auto] gap-4 p-3 text-left transition-colors hover:bg-muted focus-visible:outline-2 disabled:cursor-not-allowed disabled:bg-muted/50 disabled:text-muted-foreground",
                          isSelected && "bg-muted",
                        )}
                        type="button"
                        disabled={!option.isSelectable}
                        onClick={() => {
                          onChange(option.id);
                          setOpen(false);
                        }}
                      >
                        <span className="min-w-0">
                          <span className="block break-words text-sm font-medium">
                            {option.label}
                          </span>
                          <span className="mt-0.5 block break-words text-xs text-muted-foreground">
                            {option.description}
                          </span>
                        </span>
                        <span className="flex items-center gap-2 text-xs text-muted-foreground">
                          {option.status}
                          {isSelected ? (
                            <Check className="size-4" aria-hidden="true" />
                          ) : null}
                        </span>
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
                onClick={configureProvider}
              >
                Configure {providerCapabilityLabel(providerCapability)}
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
      </div>
    );
  },
);

function providerCapabilityFor(
  field: ProviderReferenceField,
): ProviderCapability {
  const capabilities: Record<ProviderReferenceField, ProviderCapability> = {
    emailProviderConfigId: "email",
    fileUploadEmbeddingProviderConfigId: "embedding",
    llmProviderConfigId: "llm",
    memoryProviderConfigId: "memory",
    realtimeProviderConfigId: "realtime",
    rerankingProviderConfigId: "reranking",
    storageProviderConfigId: "storage",
    sttProviderConfigId: "stt",
    ttsProviderConfigId: "tts",
    webrtcProviderConfigId: "webrtc",
  };
  return capabilities[field];
}

function providerCapabilityLabel(capability: ProviderCapability): string {
  const labels: Record<ProviderCapability, string> = {
    email: "Email",
    embedding: "Embedding",
    llm: "LLM",
    memory: "Memory",
    realtime: "Realtime",
    reranking: "Reranking",
    sandbox: "Sandbox",
    storage: "Storage",
    stt: "STT",
    telephony: "Telephony",
    tts: "TTS",
    webrtc: "WebRTC",
  };
  return labels[capability];
}

export { ProviderConfigReferenceField };
export type { ProviderConfigReferenceFieldProps };
