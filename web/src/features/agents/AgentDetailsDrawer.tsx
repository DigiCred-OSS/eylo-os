import { Pencil, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect } from "react";

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
import { AgentDateTime } from "@/features/agents/AgentDateTime";
import { AgentStatusBadge } from "@/features/agents/AgentStatusBadge";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import type {
  Agent,
  AgentReferenceField,
  AgentRevisionReference,
} from "@/features/agents/agents.types";
import type { ProviderReferenceField } from "@/features/providers/providers.types";

interface AgentDetailsDrawerProps {
  agentId: string | undefined;
  onClose: () => void;
  onEdit: (agentId: string) => void;
}

const AgentDetailsDrawer = observer(function AgentDetailsDrawer({
  agentId,
  onClose,
  onEdit,
}: AgentDetailsDrawerProps) {
  const { agents, voice } = useRootStore();
  const isOpen = agentId !== undefined;

  useEffect(() => {
    const agent = agents.selectedAgent;
    if (agent === null || agent.id !== agentId) {
      return;
    }
    void agents.references.loadAll(agent.organizationId);
    void agents.instructions.load(agent.organizationId);
    void agents.access.load(agent.organizationId, agent.id, true);
    void agents.effectiveVoice.load(agent.organizationId, agent.id);
    void voice.loadCollection(agent.organizationId);
  }, [agentId, agents, agents.selectedAgent, voice]);

  return (
    <Drawer
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,36rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle>
            {agents.selectedAgent?.name ?? "Agent details"}
          </DrawerTitle>
          <DrawerDescription>
            Current saved configuration and exact published runtime authority.
          </DrawerDescription>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close Agent details"
          title="Close"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {agents.isSelectedLoading && agents.selectedAgent === null ? (
            <AgentDetailsSkeleton />
          ) : agents.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {agents.selectedErrorMessage}
            </div>
          ) : agents.selectedAgent !== null ? (
            <AgentDetails agent={agents.selectedAgent} />
          ) : null}
        </div>
        {agents.selectedAgent !== null ? (
          <DrawerFooter className="border-t p-4">
            <Button
              onClick={() => {
                if (agents.selectedAgent !== null) {
                  onEdit(agents.selectedAgent.id);
                }
              }}
            >
              <Pencil aria-hidden="true" />
              Edit Agent
            </Button>
          </DrawerFooter>
        ) : null}
      </DrawerContent>
    </Drawer>
  );
});

const AgentDetails = observer(function AgentDetails({
  agent,
}: {
  agent: Agent;
}) {
  const { agents, voice } = useRootStore();
  const instruction = agents.instructions.templateFor(
    agent.instructionTemplateId ?? null,
  );
  const llmOverrides = agent.llmOverrides;
  const voiceConfig =
    voice.items.find((item) => item.id === agent.voiceConfigId) ?? null;

  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Status">
          <AgentStatusBadge status={agent.status} />
        </DetailRow>
        <DetailRow label="Kind">
          <Badge variant="outline">{formatAgentEnum(agent.kind)}</Badge>
        </DetailRow>
        <DetailRow label="Description">
          {agent.description?.trim() || "No description"}
        </DetailRow>
        <DetailRow label="Slug">
          <CodeValue>{agent.slug}</CodeValue>
        </DetailRow>
        <DetailRow label="Agent ID">
          <CodeValue>{agent.id}</CodeValue>
        </DetailRow>
      </DetailsSection>

      <DetailsSection title="Lifecycle">
        <DetailRow label="Definition state">
          <Badge variant="outline">{formatAgentEnum(agent.lifecycle)}</Badge>
        </DetailRow>
        <DetailRow label="Draft version">{agent.draftVersion}</DetailRow>
        <DetailRow label="Unpublished changes">
          {agent.draftDirty ? "Yes" : "No"}
        </DetailRow>
        <DetailRow label="Published revision">
          {agent.publishedRevision ?? "Not published"}
        </DetailRow>
        <DetailRow label="Created">
          <AgentDateTime value={agent.createdAt} />
        </DetailRow>
        <DetailRow label="Updated">
          <AgentDateTime value={agent.updatedAt} />
        </DetailRow>
      </DetailsSection>

      <DetailsSection title="Runtime">
        <DetailRow label="Implementation">
          {agent.implementation ?? "Prompt driven"}
        </DetailRow>
        <DetailRow label="Instruction template">
          {agent.instructionTemplateId === null ||
          agent.instructionTemplateId === undefined ? (
            "Not configured"
          ) : (
            <NamedReference
              id={agent.instructionTemplateId}
              name={instruction?.name ?? null}
              metadata={
                instruction?.published_revision === null ||
                instruction?.published_revision === undefined
                  ? null
                  : `Published revision ${instruction.published_revision}`
              }
            />
          )}
        </DetailRow>
        <DetailRow label="Webhook">
          {agent.webhook ?? "Not configured"}
        </DetailRow>
        <DetailRow label="Conversation file uploads">
          {agent.allowFileUploads ? "Allowed" : "Not allowed"}
        </DetailRow>
        <DetailRow label="Voice Config">
          {agent.voiceConfigId === null || agent.voiceConfigId === undefined ? (
            "Not configured"
          ) : (
            <NamedReference
              id={agent.voiceConfigId}
              name={voiceConfig?.name ?? null}
              metadata={
                agent.voiceConfigRevision === null ||
                agent.voiceConfigRevision === undefined
                  ? "Current Agent draft binding"
                  : `Voice Config revision ${agent.voiceConfigRevision}`
              }
            />
          )}
        </DetailRow>
      </DetailsSection>

      <EffectivePublishedVoiceStack />

      <DetailsSection title="Provider configuration">
        {providerReferences(agent).map((reference) => {
          const option = agents.references.getOption(
            reference.field,
            reference.id,
          );
          return (
            <DetailRow key={reference.label} label={reference.label}>
              {reference.id === null ? (
                "Not configured"
              ) : (
                <NamedReference
                  id={reference.id}
                  name={option?.label ?? null}
                  metadata={
                    reference.revision === null
                      ? (option?.provider ?? null)
                      : `${option?.provider ?? "Provider"} · revision ${reference.revision}`
                  }
                />
              )}
            </DetailRow>
          );
        })}
      </DetailsSection>

      <DetailsSection title="Model behavior">
        <DetailRow label="Model">
          {llmOverrides?.model ?? "Use provider config"}
        </DetailRow>
        <DetailRow label="Maximum tokens">
          {llmOverrides?.maxTokens ?? "Use provider config"}
        </DetailRow>
        <DetailRow label="Temperature">
          {llmOverrides?.temperature ?? "Use provider config"}
        </DetailRow>
        <DetailRow label="Top K">
          {llmOverrides?.topK ?? "Use provider config"}
        </DetailRow>
        <DetailRow label="Top P">
          {llmOverrides?.topP ?? "Use provider config"}
        </DetailRow>
        <DetailRow label="Stop sequences">
          {llmOverrides?.stopSequences === undefined ||
          llmOverrides.stopSequences === null ||
          llmOverrides.stopSequences.length === 0
            ? "Use provider config"
            : llmOverrides.stopSequences.join(" · ")}
        </DetailRow>
      </DetailsSection>

      <DetailsSection title="Runtime access">
        <DetailRow label="Knowledgebases">
          {agents.access.isKnowledgeLoading &&
          agents.access.knowledgebaseGrants.length === 0
            ? "Loading access…"
            : agents.access.knowledgeErrorMessage !== null &&
                agents.access.knowledgebaseGrants.length === 0
              ? "Access unavailable"
              : agents.access.knowledgebaseGrants.length === 0
                ? "None granted"
                : agents.access.knowledgebaseGrants.map((grant) => {
                    const knowledgebase = agents.access.knowledgebaseFor(
                      grant.knowledgebase_id,
                    );
                    return (
                      <div key={grant.id} className="not-last:mb-2">
                        <NamedReference
                          id={grant.knowledgebase_id}
                          name={knowledgebase?.name ?? null}
                          metadata={
                            grant.access === "read_write"
                              ? "Read + write"
                              : "Read"
                          }
                        />
                      </div>
                    );
                  })}
        </DetailRow>
        <DetailRow label="Sandbox">
          {agents.access.isSandboxLoading &&
          agents.access.sandboxGrant === null ? (
            "Loading access…"
          ) : agents.access.sandboxErrorMessage !== null &&
            agents.access.sandboxGrant === null ? (
            "Access unavailable"
          ) : agents.access.sandboxGrant === null ? (
            "Not granted"
          ) : (
            <NamedReference
              id={agents.access.sandboxGrant.sandbox_provider_config_id}
              name={
                agents.access.sandboxConfigFor(
                  agents.access.sandboxGrant.sandbox_provider_config_id,
                )?.name ?? null
              }
              metadata={
                agents.access.sandboxGrant.max_sessions === null
                  ? "Run · organization session limit"
                  : `Run · max ${agents.access.sandboxGrant.max_sessions} sessions`
              }
            />
          )}
        </DetailRow>
      </DetailsSection>
    </div>
  );
});

const EffectivePublishedVoiceStack = observer(
  function EffectivePublishedVoiceStack() {
    const { agents, voice } = useRootStore();
    const { effectiveVoice } = agents;
    const stack = effectiveVoice.stack;

    if (effectiveVoice.isLoading && stack === null) {
      return (
        <DetailsSection title="Effective published voice stack">
          <DetailRow label="State">Loading published stack…</DetailRow>
          <DetailRow label="Authority">Loading exact revisions…</DetailRow>
        </DetailsSection>
      );
    }
    if (effectiveVoice.errorMessage !== null && stack === null) {
      return (
        <DetailsSection title="Effective published voice stack">
          <DetailRow label="State">Unavailable</DetailRow>
          <DetailRow label="Reason">{effectiveVoice.errorMessage}</DetailRow>
        </DetailsSection>
      );
    }
    if (stack === null) {
      return null;
    }

    const voiceConfig =
      stack.voiceConfig === null || stack.voiceConfig === undefined
        ? null
        : (voice.items.find((item) => item.id === stack.voiceConfig?.id) ??
          null);

    return (
      <DetailsSection title="Effective published voice stack">
        <DetailRow label="State">
          <Badge variant="outline">{formatAgentEnum(stack.state)}</Badge>
        </DetailRow>
        {stack.state === "not_published" ? (
          <DetailRow label="Authority">
            Publish this Agent to create an executable voice stack.
          </DetailRow>
        ) : (
          <>
            <DetailRow label="Agent revision">
              {stack.agentRevision ?? "Unavailable"}
            </DetailRow>
            {stack.state === "text_only" ? (
              <DetailRow label="Voice">Not configured</DetailRow>
            ) : (
              <>
                <DetailRow label="Voice Config">
                  {stack.voiceConfig === null ||
                  stack.voiceConfig === undefined ? (
                    "Not configured"
                  ) : (
                    <NamedReference
                      id={stack.voiceConfig.id}
                      name={voiceConfig?.name ?? null}
                      metadata={`Revision ${stack.voiceConfig.revision}`}
                    />
                  )}
                </DetailRow>
                <EffectiveProviderRow
                  field="webrtcProviderConfigId"
                  label="WebRTC"
                  reference={stack.webrtcProvider ?? null}
                />
                {stack.state === "realtime" ? (
                  <EffectiveProviderRow
                    field="realtimeProviderConfigId"
                    label="Realtime"
                    reference={stack.realtimeProvider ?? null}
                  />
                ) : (
                  <>
                    <EffectiveProviderRow
                      field="sttProviderConfigId"
                      label="Speech to text"
                      reference={stack.sttProvider ?? null}
                    />
                    <EffectiveProviderRow
                      field="ttsProviderConfigId"
                      label="Text to speech"
                      reference={stack.ttsProvider ?? null}
                    />
                  </>
                )}
                <EffectiveProviderRow
                  field="storageProviderConfigId"
                  label="Recording storage"
                  reference={stack.storageProvider ?? null}
                />
              </>
            )}
          </>
        )}
      </DetailsSection>
    );
  },
);

const EffectiveProviderRow = observer(function EffectiveProviderRow({
  field,
  label,
  reference,
}: {
  field: ProviderReferenceField;
  label: string;
  reference: AgentRevisionReference | null;
}) {
  const { agents } = useRootStore();
  const option = agents.references.getOption(field, reference?.id ?? null);
  return (
    <DetailRow label={label}>
      {reference === null ? (
        "Not configured"
      ) : (
        <NamedReference
          id={reference.id}
          name={option?.label ?? null}
          metadata={`${option?.provider ?? "Provider"} · revision ${reference.revision}`}
        />
      )}
    </DetailRow>
  );
});

function NamedReference({
  id,
  metadata,
  name,
}: {
  id: string;
  metadata: string | null;
  name: string | null;
}) {
  return (
    <span className="block min-w-0">
      <span className="block break-words">{name ?? id}</span>
      {metadata !== null ? (
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {metadata}
        </span>
      ) : null}
      {name !== null ? (
        <code className="mt-1 block break-all text-[0.6875rem] text-muted-foreground">
          {id}
        </code>
      ) : null}
    </span>
  );
}

interface ProviderReference {
  field: AgentReferenceField;
  id: string | null;
  label: string;
  revision: number | null;
}

function providerReferences(agent: Agent): ProviderReference[] {
  return [
    {
      field: "fileUploadEmbeddingProviderConfigId",
      id: agent.fileUploadEmbeddingProviderConfigId ?? null,
      label: "File upload embedding",
      revision: agent.fileUploadEmbeddingProviderConfigRevision ?? null,
    },
    {
      field: "llmProviderConfigId",
      id: agent.llmProviderConfigId ?? null,
      label: "Language model",
      revision: agent.llmProviderConfigRevision ?? null,
    },
    {
      field: "emailProviderConfigId",
      id: agent.emailProviderConfigId ?? null,
      label: "Email",
      revision: agent.emailProviderConfigRevision ?? null,
    },
    {
      field: "webrtcProviderConfigId",
      id: agent.webrtcProviderConfigId ?? null,
      label: "WebRTC",
      revision: agent.webrtcProviderConfigRevision ?? null,
    },
    {
      field: "rerankingProviderConfigId",
      id: agent.rerankingProviderConfigId ?? null,
      label: "Reranking",
      revision: agent.rerankingProviderConfigRevision ?? null,
    },
    {
      field: "memoryProviderConfigId",
      id: agent.memoryProviderConfigId ?? null,
      label: "Memory",
      revision: agent.memoryProviderConfigRevision ?? null,
    },
  ];
}

function DetailsSection({
  children,
  title,
}: {
  children: React.ReactNode;
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
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm leading-5">{children}</dd>
    </div>
  );
}

function CodeValue({ children }: { children: React.ReactNode }) {
  return (
    <code className="break-all rounded-sm bg-muted px-1 py-0.5 text-xs">
      {children}
    </code>
  );
}

function AgentDetailsSkeleton() {
  return (
    <div className="space-y-8" aria-label="Loading Agent details">
      {[0, 1, 2].map((section) => (
        <div key={section} className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <div className="space-y-px border-y">
            {[0, 1, 2].map((row) => (
              <div key={row} className="grid grid-cols-[9rem_1fr] gap-4 py-3">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-full" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export { AgentDetailsDrawer };
