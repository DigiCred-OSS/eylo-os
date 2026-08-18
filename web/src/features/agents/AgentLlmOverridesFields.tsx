import { observer } from "mobx-react-lite";
import { useEffect } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import type {
  AgentLlmModel,
  AgentLlmOverrideValues,
} from "@/features/agents/agents.types";

const PROVIDER_MODEL = "__provider_config__";

interface AgentLlmOverridesFieldsProps {
  llmProviderConfigId: string | null;
  onChange: (value: AgentLlmOverrideValues) => void;
  values: AgentLlmOverrideValues;
}

const AgentLlmOverridesFields = observer(function AgentLlmOverridesFields({
  llmProviderConfigId,
  onChange,
  values,
}: AgentLlmOverridesFieldsProps) {
  const { agents, providers } = useRootStore();
  const selectedConfig = agents.form.references.getOption(
    "llmProviderConfigId",
    llmProviderConfigId,
  );

  useEffect(() => {
    if (providers.catalog === null && !providers.isOverviewLoading) {
      void providers.loadOverview();
    }
  }, [providers, providers.catalog, providers.isOverviewLoading]);

  const models = modelOptionsFor(providers, selectedConfig?.provider ?? null);
  const hasCurrentModel =
    values.model !== null &&
    !models.some((model) => model.value === values.model);

  function setOverride<Key extends keyof AgentLlmOverrideValues>(
    field: Key,
    value: AgentLlmOverrideValues[Key],
  ): void {
    onChange({ ...values, [field]: value });
  }

  return (
    <section className="border">
      <div className="space-y-1 p-4">
        <h3 className="text-sm font-medium">Model behavior</h3>
        <p className="text-xs leading-5 text-muted-foreground">
          Optional Agent-level overrides. Empty values inherit the selected
          provider config. Provider adapters ignore settings they do not
          support.
        </p>
      </div>
      <Separator />
      <div className="space-y-5 p-4">
        <OverrideField
          htmlFor="agent-llm-model"
          label="Model override"
          hint={
            llmProviderConfigId === null
              ? "Choose an LLM provider config before overriding its model."
              : providers.overviewErrorMessage !== null &&
                  providers.catalog === null
                ? "Provider model options could not be loaded."
                : `Models declared for ${selectedConfig?.provider ?? "the selected provider"}.`
          }
        >
          <Select
            value={values.model ?? PROVIDER_MODEL}
            disabled={
              llmProviderConfigId === null ||
              (models.length === 0 && values.model === null)
            }
            onValueChange={(value) =>
              setOverride(
                "model",
                value === PROVIDER_MODEL ? null : (value as AgentLlmModel),
              )
            }
          >
            <SelectTrigger id="agent-llm-model" className="w-full">
              <SelectValue>{values.model ?? "Use provider config"}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={PROVIDER_MODEL}>
                Use provider config
              </SelectItem>
              {hasCurrentModel ? (
                <SelectItem value={values.model ?? ""}>
                  {values.model}
                </SelectItem>
              ) : null}
              {models.map((model) => (
                <SelectItem key={model.value} value={model.value}>
                  {model.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </OverrideField>

        <div className="grid gap-5 sm:grid-cols-2">
          <NumberOverride
            id="agent-llm-max-tokens"
            label="Maximum tokens"
            min={1}
            step={1}
            value={values.maxTokens}
            onChange={(value) => setOverride("maxTokens", value)}
          />
          <NumberOverride
            id="agent-llm-temperature"
            label="Temperature"
            min={0}
            max={2}
            step={0.1}
            value={values.temperature}
            onChange={(value) => setOverride("temperature", value)}
          />
          <NumberOverride
            id="agent-llm-top-k"
            label="Top K"
            min={1}
            step={1}
            value={values.topK}
            onChange={(value) => setOverride("topK", value)}
          />
          <NumberOverride
            id="agent-llm-top-p"
            label="Top P"
            min={0}
            max={1}
            step={0.05}
            value={values.topP}
            onChange={(value) => setOverride("topP", value)}
          />
        </div>

        <OverrideField
          htmlFor="agent-llm-stop-sequences"
          label="Stop sequences"
          hint="One exact sequence per line. Empty means no Agent-level override."
        >
          <Textarea
            id="agent-llm-stop-sequences"
            rows={4}
            value={values.stopSequences.join("\n")}
            onChange={(event) =>
              setOverride(
                "stopSequences",
                parseStopSequences(event.target.value),
              )
            }
          />
        </OverrideField>
      </div>
    </section>
  );
});

function NumberOverride({
  id,
  label,
  max,
  min,
  onChange,
  step,
  value,
}: {
  id: string;
  label: string;
  max?: number;
  min: number;
  onChange: (value: number | null) => void;
  step: number;
  value: number | null;
}) {
  return (
    <OverrideField
      htmlFor={id}
      label={label}
      hint="Empty uses the provider config."
    >
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        value={value ?? ""}
        onChange={(event) => onChange(parseNumber(event.target.value))}
      />
    </OverrideField>
  );
}

function OverrideField({
  children,
  hint,
  htmlFor,
  label,
}: {
  children: React.ReactNode;
  hint: string;
  htmlFor: string;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
    </div>
  );
}

interface ModelOption {
  label: string;
  value: AgentLlmModel;
}

interface ProviderCatalogReader {
  catalog: ReturnType<typeof useRootStore>["providers"]["catalog"];
  definitionFor: ReturnType<typeof useRootStore>["providers"]["definitionFor"];
}

function modelOptionsFor(
  providers: ProviderCatalogReader,
  providerId: string | null,
): ModelOption[] {
  if (providerId === null) {
    return [];
  }
  const provider = providers
    .definitionFor("llm")
    ?.providers.find((definition) => definition.id === providerId);
  const modelField = provider?.fields.find((field) => field.key === "model");
  return (modelField?.options ?? []).map((option) => ({
    label: option.label,
    value: option.value as AgentLlmModel,
  }));
}

function parseNumber(value: string): number | null {
  return value === "" ? null : Number(value);
}

function parseStopSequences(value: string): string[] {
  return value === ""
    ? []
    : value.split("\n").filter((sequence) => sequence !== "");
}

export { AgentLlmOverridesFields };
