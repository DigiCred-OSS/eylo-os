import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { getAgentApiErrorMessage } from "@/features/agents/agent-api-errors";
import type { AgentFormStore } from "@/features/agents/agent-form.store";
import type {
  Agent,
  AgentBackgroundAttachment,
  AgentCuratedTool,
  Tool,
} from "@/features/agents/agents.types";

const TOOLS_LOAD_ERROR = "Agent tools could not be loaded. Try again.";
const BACKGROUNDS_LOAD_ERROR =
  "Background Agent attachments could not be loaded. Try again.";
const CURATED_TOOLS_LOAD_ERROR =
  "Integration tools could not be loaded. Try again.";
const RELATIONSHIP_ACTION_ERROR =
  "The relationship could not be changed. Try again.";
const RELATIONSHIP_CONFLICT_ERROR =
  "The Agent changed while this relationship was being saved. Relationships were refreshed; try again.";

class AgentRelationshipsStore {
  actionErrorMessage: string | null = null;
  assignedTools: Tool[] = [];
  assignedCuratedTools: AgentCuratedTool[] = [];
  attachments: AgentBackgroundAttachment[] = [];
  availableBackgroundAgents: Agent[] = [];
  availableTools: Tool[] = [];
  availableCuratedTools: AgentCuratedTool[] = [];
  backgroundsErrorMessage: string | null = null;
  isActing = false;
  isBackgroundsLoading = false;
  isCuratedToolsLoading = false;
  isToolsLoading = false;
  systemCatalogToolIds = new Set<string>();
  curatedToolsErrorMessage: string | null = null;
  toolsErrorMessage: string | null = null;

  private readonly api: ApiClient;
  private contextKey: string | null = null;
  private readonly form: AgentFormStore;
  private loadVersion = 0;

  constructor(api: ApiClient, form: AgentFormStore) {
    this.api = api;
    this.form = form;

    makeAutoObservable<this, "api" | "contextKey" | "form" | "loadVersion">(
      this,
      {
        api: false,
        contextKey: false,
        form: false,
        loadVersion: false,
      },
      { autoBind: true },
    );
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
      this.assignedTools = [];
      this.assignedCuratedTools = [];
      this.attachments = [];
      this.availableBackgroundAgents = [];
      this.availableTools = [];
      this.availableCuratedTools = [];
      this.systemCatalogToolIds = new Set<string>();
    }
    this.actionErrorMessage = null;

    await Promise.all([
      this.loadTools(organizationId, agentId, contextKey, loadVersion),
      this.loadCuratedTools(organizationId, agentId, contextKey, loadVersion),
      this.loadBackgrounds(organizationId, agentId, contextKey, loadVersion),
    ]);
  }

  private async loadCuratedTools(
    organizationId: string,
    agentId: string,
    contextKey: string,
    loadVersion: number,
  ): Promise<void> {
    this.isCuratedToolsLoading = true;
    this.curatedToolsErrorMessage = null;
    try {
      const [installationsResult, assignedResult] = await Promise.all([
        this.api.GET("/api/{organization_id}/curated-integrations", {
          params: { path: { organization_id: organizationId } },
        }),
        this.api.GET("/api/{organization_id}/agents/{agent_id}/curated-tools", {
          params: {
            path: { organization_id: organizationId, agent_id: agentId },
          },
        }),
      ]);
      if (
        !installationsResult.response.ok ||
        installationsResult.data === undefined ||
        !assignedResult.response.ok ||
        assignedResult.data === undefined
      ) {
        throw new Error(CURATED_TOOLS_LOAD_ERROR);
      }
      const installations = installationsResult.data;
      const toolResults = await Promise.all(
        installations.map((installation) =>
          this.api.GET(
            "/api/{organization_id}/curated-vendors/{vendor}/tools",
            {
              params: {
                path: {
                  organization_id: organizationId,
                  vendor: installation.vendor,
                },
              },
            },
          ),
        ),
      );
      if (toolResults.some((result) => !result.response.ok || !result.data)) {
        throw new Error(CURATED_TOOLS_LOAD_ERROR);
      }
      if (!this.isCurrentLoad(contextKey, loadVersion)) return;
      const labels = new Map(
        installations.map((installation) => [
          installation.vendor,
          installation.displayName,
        ]),
      );
      runInAction(() => {
        this.availableCuratedTools = toolResults.flatMap((result) =>
          (result.data ?? []).map((tool) => decorateCuratedTool(tool, labels)),
        );
        this.assignedCuratedTools = assignedResult.data.map((tool) =>
          decorateCuratedTool(tool, labels),
        );
      });
    } catch {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.curatedToolsErrorMessage = CURATED_TOOLS_LOAD_ERROR;
        });
      }
    } finally {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.isCuratedToolsLoading = false;
        });
      }
    }
  }

  private async loadTools(
    organizationId: string,
    agentId: string,
    contextKey: string,
    loadVersion: number,
  ): Promise<void> {
    this.isToolsLoading = true;
    this.toolsErrorMessage = null;

    try {
      const [catalog, tools, assigned] = await Promise.all([
        this.api.GET("/api/{organization_id}/tools/system-catalog", {
          params: { path: { organization_id: organizationId } },
        }),
        this.api.GET("/api/{organization_id}/tools", {
          params: { path: { organization_id: organizationId } },
        }),
        this.api.GET("/api/{organization_id}/agents/{agent_id}/tools", {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
            },
          },
        }),
      ]);

      if (
        !catalog.response.ok ||
        catalog.data === undefined ||
        !tools.response.ok ||
        tools.data === undefined ||
        !assigned.response.ok ||
        assigned.data === undefined
      ) {
        throw new Error(TOOLS_LOAD_ERROR);
      }

      if (!this.isCurrentLoad(contextKey, loadVersion)) {
        return;
      }

      const availableTools = deduplicateTools([
        ...catalog.data.items,
        ...tools.data.items,
      ]);

      runInAction(() => {
        this.availableTools = availableTools;
        this.assignedTools = assigned.data.items;
        this.systemCatalogToolIds = new Set(
          catalog.data.items.map((tool) => tool.id),
        );
      });
    } catch {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.toolsErrorMessage = TOOLS_LOAD_ERROR;
        });
      }
    } finally {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.isToolsLoading = false;
        });
      }
    }
  }

  private async loadBackgrounds(
    organizationId: string,
    agentId: string,
    contextKey: string,
    loadVersion: number,
  ): Promise<void> {
    this.isBackgroundsLoading = true;
    this.backgroundsErrorMessage = null;

    try {
      const [backgrounds, attachments] = await Promise.all([
        this.api.GET("/api/{organization_id}/agents", {
          params: {
            path: { organization_id: organizationId },
            query: { kind: ["BACKGROUND"], limit: 100, page: 1 },
          },
        }),
        this.api.GET(
          "/api/{organization_id}/agents/{agent_id}/background-agents",
          {
            params: {
              path: {
                organization_id: organizationId,
                agent_id: agentId,
              },
            },
          },
        ),
      ]);
      if (
        !backgrounds.response.ok ||
        backgrounds.data === undefined ||
        !attachments.response.ok ||
        attachments.data === undefined
      ) {
        throw new Error(BACKGROUNDS_LOAD_ERROR);
      }
      if (!this.isCurrentLoad(contextKey, loadVersion)) {
        return;
      }
      runInAction(() => {
        this.availableBackgroundAgents = backgrounds.data.data;
        this.attachments = attachments.data;
      });
    } catch {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.backgroundsErrorMessage = BACKGROUNDS_LOAD_ERROR;
        });
      }
    } finally {
      if (this.isCurrentLoad(contextKey, loadVersion)) {
        runInAction(() => {
          this.isBackgroundsLoading = false;
        });
      }
    }
  }

  async assignTool(
    organizationId: string,
    agentId: string,
    toolId: string,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.POST(
        "/api/{organization_id}/agents/{agent_id}/tools",
        {
          params: {
            path: { organization_id: organizationId, agent_id: agentId },
          },
          body: {
            toolId,
            expectedDraftVersion: agent.draftVersion,
          },
        },
      );
      return { error, response };
    });
  }

  async removeTool(
    organizationId: string,
    agentId: string,
    toolId: string,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.DELETE(
        "/api/{organization_id}/agents/{agent_id}/tools/{tool_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
              tool_id: toolId,
            },
            query: { expected_draft_version: agent.draftVersion },
          },
        },
      );
      return { error, response };
    });
  }

  async assignCuratedTool(
    organizationId: string,
    agentId: string,
    tool: AgentCuratedTool,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.POST(
        "/api/{organization_id}/agents/{agent_id}/curated-tools/{vendor}/{tool_name}",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
              vendor: tool.vendor,
              tool_name: tool.name,
            },
          },
          body: { expectedDraftVersion: agent.draftVersion },
        },
      );
      return { error, response };
    });
  }

  async replaceCuratedTools(
    organizationId: string,
    agentId: string,
    tools: readonly AgentCuratedTool[],
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.PUT(
        "/api/{organization_id}/agents/{agent_id}/curated-tools",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
            },
          },
          body: {
            expectedDraftVersion: agent.draftVersion,
            toolIds: tools.map((tool) => tool.id),
          },
        },
      );
      return { error, response };
    });
  }

  async removeCuratedTool(
    organizationId: string,
    agentId: string,
    tool: AgentCuratedTool,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.DELETE(
        "/api/{organization_id}/agents/{agent_id}/curated-tools/{vendor}/{tool_name}",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
              vendor: tool.vendor,
              tool_name: tool.name,
            },
            query: { expected_draft_version: agent.draftVersion },
          },
        },
      );
      return { error, response };
    });
  }

  async attachBackgroundAgent(
    organizationId: string,
    agentId: string,
    backgroundAgentId: string,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.POST(
        "/api/{organization_id}/agents/{agent_id}/background-agents",
        {
          params: {
            path: { organization_id: organizationId, agent_id: agentId },
          },
          body: {
            background_agent_id: backgroundAgentId,
            expected_draft_version: agent.draftVersion,
          },
        },
      );
      return { error, response };
    });
  }

  async setBackgroundAgentEnabled(
    organizationId: string,
    agentId: string,
    backgroundAgentId: string,
    enabled: boolean,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.PATCH(
        "/api/{organization_id}/agents/{agent_id}/background-agents/{background_agent_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
              background_agent_id: backgroundAgentId,
            },
          },
          body: {
            enabled,
            expected_draft_version: agent.draftVersion,
          },
        },
      );
      return { error, response };
    });
  }

  async detachBackgroundAgent(
    organizationId: string,
    agentId: string,
    backgroundAgentId: string,
  ): Promise<boolean> {
    return this.runAction(organizationId, agentId, async (agent) => {
      const { error, response } = await this.api.DELETE(
        "/api/{organization_id}/agents/{agent_id}/background-agents/{background_agent_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              agent_id: agentId,
              background_agent_id: backgroundAgentId,
            },
            query: { expected_draft_version: agent.draftVersion },
          },
        },
      );
      return { error, response };
    });
  }

  private async runAction(
    organizationId: string,
    agentId: string,
    action: (agent: Agent) => Promise<ActionResponse>,
  ): Promise<boolean> {
    const contextKey = buildContextKey(organizationId, agentId);
    if (this.isActing || !this.isCurrentContext(contextKey)) {
      return false;
    }

    this.isActing = true;
    this.actionErrorMessage = null;

    try {
      const currentAgent = this.form.serverAgent;
      if (currentAgent === null) {
        runInAction(() => {
          this.actionErrorMessage = RELATIONSHIP_ACTION_ERROR;
        });
        return false;
      }

      const { error, response } = await action(currentAgent);
      if (!this.isCurrentAction(contextKey, organizationId, agentId)) {
        return false;
      }
      if (!response.ok) {
        await this.handleActionError(
          organizationId,
          agentId,
          contextKey,
          response.status,
          error,
        );
        return false;
      }

      const updatedAgent = await this.fetchAgent(organizationId, agentId);
      if (!this.isCurrentAction(contextKey, organizationId, agentId)) {
        return false;
      }
      if (updatedAgent === null) {
        runInAction(() => {
          this.actionErrorMessage = RELATIONSHIP_ACTION_ERROR;
        });
        return false;
      }

      runInAction(() => {
        this.form.synchronizeAfterRelatedWrite(updatedAgent);
      });
      await this.load(organizationId, agentId, true);
      return this.isCurrentAction(contextKey, organizationId, agentId);
    } catch {
      if (this.isCurrentContext(contextKey)) {
        runInAction(() => {
          this.actionErrorMessage = RELATIONSHIP_ACTION_ERROR;
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  private async handleActionError(
    organizationId: string,
    agentId: string,
    contextKey: string,
    status: number,
    error: unknown,
  ): Promise<void> {
    if (!this.isCurrentAction(contextKey, organizationId, agentId)) {
      return;
    }
    if (status === 409) {
      const latestAgent = await this.fetchAgent(organizationId, agentId);
      if (!this.isCurrentAction(contextKey, organizationId, agentId)) {
        return;
      }
      if (latestAgent !== null) {
        runInAction(() => {
          this.form.synchronizeAfterRelatedWrite(latestAgent);
        });
      }
      await this.load(organizationId, agentId, true);
      if (!this.isCurrentAction(contextKey, organizationId, agentId)) {
        return;
      }
      runInAction(() => {
        this.actionErrorMessage = RELATIONSHIP_CONFLICT_ERROR;
      });
      return;
    }

    runInAction(() => {
      this.actionErrorMessage = getAgentApiErrorMessage(
        error,
        RELATIONSHIP_ACTION_ERROR,
      );
    });
  }

  private isCurrentAction(
    contextKey: string,
    organizationId: string,
    agentId: string,
  ): boolean {
    return (
      this.isCurrentContext(contextKey) &&
      this.form.matchesEditContext(organizationId, agentId)
    );
  }

  private isCurrentContext(contextKey: string): boolean {
    return this.contextKey === contextKey;
  }

  private isCurrentLoad(contextKey: string, loadVersion: number): boolean {
    return (
      this.isCurrentContext(contextKey) && this.loadVersion === loadVersion
    );
  }

  private async fetchAgent(
    organizationId: string,
    agentId: string,
  ): Promise<Agent | null> {
    const { data, response } = await this.api.GET(
      "/api/{organization_id}/agents/{agent_id}",
      {
        params: {
          path: { organization_id: organizationId, agent_id: agentId },
        },
      },
    );
    return response.ok && data !== undefined ? data : null;
  }
}

interface ActionResponse {
  error: unknown;
  response: Response;
}

function deduplicateTools(tools: readonly Tool[]): Tool[] {
  return Array.from(new Map(tools.map((tool) => [tool.id, tool])).values());
}

function decorateCuratedTool(
  tool: Omit<AgentCuratedTool, "vendor" | "vendorDisplayName">,
  labels: ReadonlyMap<string, string>,
): AgentCuratedTool {
  const vendor = tool.wireId.split(".", 1)[0] ?? "unknown";
  return {
    ...tool,
    vendor,
    vendorDisplayName: labels.get(vendor) ?? vendor,
  };
}

function buildContextKey(organizationId: string, agentId: string): string {
  return `${organizationId}:${agentId}`;
}

export { AgentRelationshipsStore };
