import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { AgentAccessStore } from "@/features/agents/agent-access.store";
import { AgentEffectiveVoiceStore } from "@/features/agents/agent-effective-voice.store";
import { getAgentApiErrorMessage } from "@/features/agents/agent-api-errors";
import { AgentDraftStorage } from "@/features/agents/agent-draft-storage";
import { AgentFormStore } from "@/features/agents/agent-form.store";
import { AgentInstructionDraftStorage } from "@/features/agents/agent-instruction-draft-storage";
import { AgentInstructionsStore } from "@/features/agents/agent-instructions.store";
import { AgentLifecycleStore } from "@/features/agents/agent-lifecycle.store";
import { AgentReferencesStore } from "@/features/agents/agent-references.store";
import { AgentRelationshipsStore } from "@/features/agents/agent-relationships.store";
import { toAgentListApiQuery } from "@/features/agents/agents.query";
import type {
  Agent,
  AgentCollectionQuery,
} from "@/features/agents/agents.types";

const COLLECTION_ERROR_MESSAGE =
  "Agents could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR_MESSAGE =
  "This Agent could not be loaded. It may no longer exist.";
const DELETE_ERROR_MESSAGE = "The Agent could not be deleted. Try again.";
const DELETE_RETAINED_MESSAGE =
  "This Agent has published revisions and is retained for audit and durable-run references.";

class AgentsStore {
  collectionErrorMessage: string | null = null;
  deleteErrorMessage: string | null = null;
  hasMore = false;
  isCollectionLoading = false;
  isDeleting = false;
  isSelectedLoading = false;
  items: Agent[] = [];
  limit = 20;
  page = 1;
  selectedAgent: Agent | null = null;
  selectedErrorMessage: string | null = null;
  total = 0;

  readonly access: AgentAccessStore;
  readonly effectiveVoice: AgentEffectiveVoiceStore;
  readonly form: AgentFormStore;
  readonly instructions: AgentInstructionsStore;
  readonly lifecycle: AgentLifecycleStore;
  readonly references: AgentReferencesStore;
  readonly relationships: AgentRelationshipsStore;

  private readonly api: ApiClient;
  private collectionRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;

  constructor(
    api: ApiClient,
    draftStorage: AgentDraftStorage,
    instructionDraftStorage: AgentInstructionDraftStorage,
  ) {
    this.api = api;
    this.access = new AgentAccessStore(api);
    this.effectiveVoice = new AgentEffectiveVoiceStore(api);
    this.references = new AgentReferencesStore(api);
    this.form = new AgentFormStore(api, draftStorage, this.references);
    this.instructions = new AgentInstructionsStore(
      api,
      instructionDraftStorage,
    );
    this.lifecycle = new AgentLifecycleStore(api, this.form);
    this.relationships = new AgentRelationshipsStore(api, this.form);

    makeAutoObservable<this, "api" | "collectionRequest" | "selectedRequest">(
      this,
      {
        access: false,
        api: false,
        collectionRequest: false,
        form: false,
        effectiveVoice: false,
        instructions: false,
        lifecycle: false,
        references: false,
        relationships: false,
        selectedRequest: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(
    organizationId: string,
    query: AgentCollectionQuery,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    this.items = [];
    this.total = 0;

    try {
      const { data, response } = await this.api.GET(
        "/api/{organization_id}/agents",
        {
          params: {
            path: { organization_id: organizationId },
            query: toAgentListApiQuery(query),
          },
          signal: request.signal,
        },
      );

      if (!response.ok || data === undefined) {
        throw new Error("Agents collection request failed");
      }

      if (request.signal.aborted) {
        return;
      }

      runInAction(() => {
        this.items = data.data;
        this.page = data.page;
        this.limit = data.limit;
        this.total = data.total ?? data.data.length;
        this.hasMore = data.hasMore ?? false;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.collectionErrorMessage = COLLECTION_ERROR_MESSAGE;
        });
      }
    } finally {
      if (this.collectionRequest === request) {
        runInAction(() => {
          this.collectionRequest = null;
          this.isCollectionLoading = false;
        });
      }
    }
  }

  async loadAgent(organizationId: string, agentId: string): Promise<void> {
    this.selectedRequest?.abort();
    const request = new AbortController();
    this.selectedRequest = request;
    this.selectedAgent =
      this.items.find((agent) => agent.id === agentId) ?? null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;

    try {
      const { data, response } = await this.api.GET(
        "/api/{organization_id}/agents/{agent_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
            },
          },
          signal: request.signal,
        },
      );

      if (!response.ok || data === undefined) {
        throw new Error("Agent detail request failed");
      }

      if (request.signal.aborted) {
        return;
      }

      runInAction(() => {
        this.selectedAgent = data;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.selectedAgent = null;
          this.selectedErrorMessage = DETAIL_ERROR_MESSAGE;
        });
      }
    } finally {
      if (this.selectedRequest === request) {
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
      }
    }
  }

  clearSelectedAgent(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedAgent = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
    this.effectiveVoice.clear();
  }

  clearDeleteError(): void {
    this.deleteErrorMessage = null;
  }

  async deleteAgent(organizationId: string, agentId: string): Promise<boolean> {
    if (this.isDeleting) {
      return false;
    }

    this.isDeleting = true;
    this.deleteErrorMessage = null;

    try {
      const { data, error, response } = await this.api.DELETE(
        "/api/{organization_id}/agents/{agent_id}",
        {
          params: {
            path: { organization_id: organizationId, agent_id: agentId },
          },
        },
      );

      if (!response.ok || data === undefined) {
        runInAction(() => {
          this.deleteErrorMessage = getAgentApiErrorMessage(
            error,
            DELETE_ERROR_MESSAGE,
          );
        });
        return false;
      }

      if (!data.deleted) {
        runInAction(() => {
          this.deleteErrorMessage = DELETE_RETAINED_MESSAGE;
        });
        return false;
      }

      return true;
    } catch {
      runInAction(() => {
        this.deleteErrorMessage = DELETE_ERROR_MESSAGE;
      });
      return false;
    } finally {
      runInAction(() => {
        this.isDeleting = false;
      });
    }
  }
}

export { AgentsStore };
