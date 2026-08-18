import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { getAgentApiErrorMessage } from "@/features/agents/agent-api-errors";
import type {
  AgentKnowledgeAccess,
  AgentKnowledgebase,
  AgentKnowledgebaseGrant,
  AgentSandboxConfig,
  AgentSandboxGrant,
} from "@/features/agents/agents.types";

const KNOWLEDGE_LOAD_ERROR_MESSAGE =
  "Agent knowledge access could not be loaded. Try again.";
const SANDBOX_LOAD_ERROR_MESSAGE =
  "Agent sandbox access could not be loaded. Try again.";
const ACTION_ERROR_MESSAGE =
  "The Agent access change could not be saved. Try again.";

class AgentAccessStore {
  actionErrorMessage: string | null = null;
  isActing = false;
  isKnowledgeLoading = false;
  isSandboxLoading = false;
  knowledgeErrorMessage: string | null = null;
  knowledgebaseGrants: AgentKnowledgebaseGrant[] = [];
  knowledgebases: AgentKnowledgebase[] = [];
  sandboxErrorMessage: string | null = null;
  sandboxConfigs: AgentSandboxConfig[] = [];
  sandboxGrant: AgentSandboxGrant | null = null;

  private readonly api: ApiClient;
  private contextKey: string | null = null;
  private loadVersion = 0;

  constructor(api: ApiClient) {
    this.api = api;
    makeAutoObservable<this, "api" | "contextKey" | "loadVersion">(
      this,
      { api: false, contextKey: false, loadVersion: false },
      { autoBind: true },
    );
  }

  knowledgebaseFor(id: string): AgentKnowledgebase | null {
    return (
      this.knowledgebases.find((knowledgebase) => knowledgebase.id === id) ??
      null
    );
  }

  sandboxConfigFor(id: string): AgentSandboxConfig | null {
    return this.sandboxConfigs.find((config) => config.id === id) ?? null;
  }

  async load(
    organizationId: string,
    agentId: string,
    force = false,
  ): Promise<void> {
    const contextKey = buildContextKey(organizationId, agentId);
    if (!force && this.contextKey === contextKey) {
      return;
    }

    const contextChanged = this.contextKey !== contextKey;
    this.contextKey = contextKey;
    const loadVersion = ++this.loadVersion;
    if (contextChanged) {
      this.knowledgebases = [];
      this.knowledgebaseGrants = [];
      this.sandboxConfigs = [];
      this.sandboxGrant = null;
    }
    this.actionErrorMessage = null;

    await Promise.all([
      this.loadKnowledge(organizationId, agentId, contextKey, loadVersion),
      this.loadSandbox(organizationId, agentId, contextKey, loadVersion),
    ]);
  }

  clearActionError(): void {
    this.actionErrorMessage = null;
  }

  async grantKnowledgebase(
    organizationId: string,
    agentId: string,
    knowledgebaseId: string,
    access: AgentKnowledgeAccess,
  ): Promise<boolean> {
    const contextKey = buildContextKey(organizationId, agentId);
    return this.runAction(
      contextKey,
      async () => {
        const { data, error, response } = await this.api.POST(
          "/api/{organization_id}/knowledgebases/grants",
          {
            params: { path: { organization_id: organizationId } },
            body: {
              access,
              agent_id: agentId,
              knowledgebase_id: knowledgebaseId,
            },
          },
        );
        if (!response.ok || data === undefined) {
          throw apiActionError(error, response);
        }
        return data;
      },
      (grant) => {
        this.knowledgebaseGrants = replaceKnowledgebaseGrant(
          this.knowledgebaseGrants,
          grant,
        );
      },
    );
  }

  async revokeKnowledgebase(
    organizationId: string,
    agentId: string,
    knowledgebaseId: string,
  ): Promise<boolean> {
    const contextKey = buildContextKey(organizationId, agentId);
    return this.runAction(
      contextKey,
      async () => {
        const { error, response } = await this.api.DELETE(
          "/api/{organization_id}/knowledgebases/grants/{agent_id}/{knowledgebase_id}",
          {
            params: {
              path: {
                agent_id: agentId,
                knowledgebase_id: knowledgebaseId,
                organization_id: organizationId,
              },
            },
          },
        );
        if (!response.ok) {
          throw apiActionError(error, response);
        }
      },
      () => {
        this.knowledgebaseGrants = this.knowledgebaseGrants.filter(
          (grant) => grant.knowledgebase_id !== knowledgebaseId,
        );
      },
    );
  }

  async grantSandbox(
    organizationId: string,
    agentId: string,
    sandboxProviderConfigId: string,
    maxSessions: number | null,
  ): Promise<boolean> {
    const contextKey = buildContextKey(organizationId, agentId);
    return this.runAction(
      contextKey,
      async () => {
        const { data, error, response } = await this.api.POST(
          "/api/{organization_id}/sandboxes/grants",
          {
            params: { path: { organization_id: organizationId } },
            body: {
              access: "run",
              agent_id: agentId,
              max_sessions: maxSessions,
              sandbox_provider_config_id: sandboxProviderConfigId,
            },
          },
        );
        if (!response.ok || data === undefined) {
          throw apiActionError(error, response);
        }
        return data;
      },
      (grant) => {
        this.sandboxGrant = grant;
      },
    );
  }

  async revokeSandbox(
    organizationId: string,
    agentId: string,
  ): Promise<boolean> {
    const contextKey = buildContextKey(organizationId, agentId);
    return this.runAction(
      contextKey,
      async () => {
        const { error, response } = await this.api.DELETE(
          "/api/{organization_id}/sandboxes/grants/{agent_id}",
          {
            params: {
              path: { agent_id: agentId, organization_id: organizationId },
            },
          },
        );
        if (!response.ok) {
          throw apiActionError(error, response);
        }
      },
      () => {
        this.sandboxGrant = null;
      },
    );
  }

  private async runAction<Result>(
    contextKey: string,
    operation: () => Promise<Result>,
    apply: (result: Result) => void,
  ): Promise<boolean> {
    if (this.isActing || this.contextKey !== contextKey) {
      return false;
    }
    this.isActing = true;
    this.actionErrorMessage = null;

    try {
      const result = await operation();
      if (this.contextKey !== contextKey) {
        return false;
      }
      runInAction(() => {
        apply(result);
      });
      return true;
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.actionErrorMessage =
            error instanceof AgentAccessActionError
              ? error.message
              : ACTION_ERROR_MESSAGE;
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  private async loadKnowledge(
    organizationId: string,
    agentId: string,
    contextKey: string,
    loadVersion: number,
  ): Promise<void> {
    this.isKnowledgeLoading = true;
    this.knowledgeErrorMessage = null;
    try {
      const [knowledgebases, grants] = await Promise.all([
        this.api.GET("/api/{organization_id}/knowledgebases", {
          params: { path: { organization_id: organizationId } },
        }),
        this.api.GET(
          "/api/{organization_id}/knowledgebases/grants/{agent_id}",
          {
            params: {
              path: {
                agent_id: agentId,
                organization_id: organizationId,
              },
            },
          },
        ),
      ]);
      if (
        !knowledgebases.response.ok ||
        knowledgebases.data === undefined ||
        !grants.response.ok ||
        grants.data === undefined
      ) {
        throw new Error(KNOWLEDGE_LOAD_ERROR_MESSAGE);
      }
      if (!this.isCurrentLoad(contextKey, loadVersion)) {
        return;
      }
      runInAction(() => {
        this.knowledgebases = knowledgebases.data;
        this.knowledgebaseGrants = grants.data;
      });
    } catch {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.knowledgeErrorMessage = KNOWLEDGE_LOAD_ERROR_MESSAGE;
        });
      }
    } finally {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.isKnowledgeLoading = false;
        });
      }
    }
  }

  private async loadSandbox(
    organizationId: string,
    agentId: string,
    contextKey: string,
    loadVersion: number,
  ): Promise<void> {
    this.isSandboxLoading = true;
    this.sandboxErrorMessage = null;
    try {
      const [configs, grants] = await Promise.all([
        this.api.GET("/api/sandbox-configs"),
        this.api.GET("/api/{organization_id}/sandboxes/grants", {
          params: { path: { organization_id: organizationId } },
        }),
      ]);
      if (
        !configs.response.ok ||
        configs.data === undefined ||
        !grants.response.ok ||
        grants.data === undefined
      ) {
        throw new Error(SANDBOX_LOAD_ERROR_MESSAGE);
      }
      if (!this.isCurrentLoad(contextKey, loadVersion)) {
        return;
      }
      runInAction(() => {
        this.sandboxConfigs = configs.data;
        this.sandboxGrant =
          grants.data.find((grant) => grant.agent_id === agentId) ?? null;
      });
    } catch {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.sandboxErrorMessage = SANDBOX_LOAD_ERROR_MESSAGE;
        });
      }
    } finally {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.isSandboxLoading = false;
        });
      }
    }
  }

  private isCurrentLoad(contextKey: string, loadVersion: number): boolean {
    return this.contextKey === contextKey && this.loadVersion === loadVersion;
  }
}

class AgentAccessActionError extends Error {}

function apiActionError(error: unknown, response: Response): Error {
  return new AgentAccessActionError(
    getAgentApiErrorMessage(
      error,
      response.status === 404
        ? "That Agent or access resource no longer exists."
        : ACTION_ERROR_MESSAGE,
    ),
  );
}

function replaceKnowledgebaseGrant(
  grants: readonly AgentKnowledgebaseGrant[],
  replacement: AgentKnowledgebaseGrant,
): AgentKnowledgebaseGrant[] {
  return [
    replacement,
    ...grants.filter(
      (grant) => grant.knowledgebase_id !== replacement.knowledgebase_id,
    ),
  ];
}

function buildContextKey(organizationId: string, agentId: string): string {
  return `${organizationId}:${agentId}`;
}

export { AgentAccessStore };
