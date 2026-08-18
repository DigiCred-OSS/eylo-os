import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { getAgentApiErrorMessage } from "@/features/agents/agent-api-errors";
import type { AgentFormStore } from "@/features/agents/agent-form.store";
import type { Agent } from "@/features/agents/agents.types";

const LIFECYCLE_ACTION_ERROR =
  "The Agent lifecycle could not be changed. Try again.";
const LIFECYCLE_CONFLICT_ERROR =
  "The Agent changed before this action completed. Its latest state is loaded; review it and try again.";

class AgentLifecycleStore {
  errorMessage: string | null = null;
  isActing = false;
  noticeMessage: string | null = null;

  private readonly api: ApiClient;
  private readonly form: AgentFormStore;

  constructor(api: ApiClient, form: AgentFormStore) {
    this.api = api;
    this.form = form;

    makeAutoObservable<this, "api" | "form">(
      this,
      { api: false, form: false },
      { autoBind: true },
    );
  }

  async publish(organizationId: string, agentId: string): Promise<boolean> {
    const agent = await this.runAction(
      organizationId,
      agentId,
      async (currentAgent) => {
        const { data, error, response } = await this.api.PUT(
          "/api/{organization_id}/agents/{agent_id}/publish",
          {
            params: {
              path: { organization_id: organizationId, agent_id: agentId },
            },
            body: { expectedDraftVersion: currentAgent.draftVersion },
          },
        );
        return { data, error, response };
      },
    );

    if (agent !== null) {
      runInAction(() => {
        this.noticeMessage =
          agent.publishedRevision == null
            ? "Agent published."
            : `Published revision ${agent.publishedRevision}.`;
      });
      return true;
    }
    return false;
  }

  async withdraw(organizationId: string, agentId: string): Promise<boolean> {
    const agent = await this.runAction(organizationId, agentId, async () => {
      const { data, error, response } = await this.api.PUT(
        "/api/{organization_id}/agents/{agent_id}/unpublish",
        {
          params: {
            path: { organization_id: organizationId, agent_id: agentId },
          },
        },
      );
      return { data, error, response };
    });

    if (agent !== null) {
      runInAction(() => {
        this.noticeMessage = "Agent withdrawn from new work.";
      });
      return true;
    }
    return false;
  }

  async revoke(
    organizationId: string,
    agentId: string,
    revision: number,
    reason: string,
  ): Promise<boolean> {
    const agent = await this.runAction(organizationId, agentId, async () => {
      const { data, error, response } = await this.api.POST(
        "/api/{organization_id}/agents/{agent_id}/revisions/revoke",
        {
          params: {
            path: { organization_id: organizationId, agent_id: agentId },
          },
          body: { reason: reason.trim(), revision },
        },
      );
      return { data, error, response };
    });

    if (agent !== null) {
      runInAction(() => {
        this.noticeMessage = `Revision ${revision} revoked.`;
      });
      return true;
    }
    return false;
  }

  clearMessages(): void {
    this.errorMessage = null;
    this.noticeMessage = null;
  }

  private async runAction(
    organizationId: string,
    agentId: string,
    action: (agent: Agent) => Promise<LifecycleResponse>,
  ): Promise<Agent | null> {
    if (this.isActing || !this.isCurrentContext(organizationId, agentId)) {
      return null;
    }

    this.isActing = true;
    this.errorMessage = null;
    this.noticeMessage = null;

    try {
      const currentAgent = await this.fetchAgent(organizationId, agentId);
      if (!this.isCurrentContext(organizationId, agentId)) {
        return null;
      }
      if (currentAgent === null) {
        runInAction(() => {
          this.errorMessage = LIFECYCLE_ACTION_ERROR;
        });
        return null;
      }

      const { data, error, response } = await action(currentAgent);
      if (!this.isCurrentContext(organizationId, agentId)) {
        return null;
      }
      if (!response.ok || data === undefined) {
        await this.handleActionError(
          organizationId,
          agentId,
          response.status,
          error,
        );
        return null;
      }

      runInAction(() => {
        this.form.synchronizeAfterRelatedWrite(data);
      });
      return data;
    } catch {
      if (this.isCurrentContext(organizationId, agentId)) {
        runInAction(() => {
          this.errorMessage = LIFECYCLE_ACTION_ERROR;
        });
      }
      return null;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  private async handleActionError(
    organizationId: string,
    agentId: string,
    status: number,
    error: unknown,
  ): Promise<void> {
    if (!this.isCurrentContext(organizationId, agentId)) {
      return;
    }
    if (status === 409) {
      const latestAgent = await this.fetchAgent(organizationId, agentId);
      if (!this.isCurrentContext(organizationId, agentId)) {
        return;
      }
      if (latestAgent !== null) {
        runInAction(() => {
          this.form.synchronizeAfterRelatedWrite(latestAgent);
        });
      }
      runInAction(() => {
        this.errorMessage = LIFECYCLE_CONFLICT_ERROR;
      });
      return;
    }

    runInAction(() => {
      this.errorMessage = getAgentApiErrorMessage(
        error,
        LIFECYCLE_ACTION_ERROR,
      );
    });
  }

  private isCurrentContext(organizationId: string, agentId: string): boolean {
    return this.form.matchesEditContext(organizationId, agentId);
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

interface LifecycleResponse {
  data: Agent | undefined;
  error: unknown;
  response: Response;
}

export { AgentLifecycleStore };
