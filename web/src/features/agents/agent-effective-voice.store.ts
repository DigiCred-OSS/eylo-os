import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import type { AgentEffectiveVoiceStack } from "@/features/agents/agents.types";

const LOAD_ERROR_MESSAGE =
  "The published voice stack could not be loaded. Try again.";

class AgentEffectiveVoiceStore {
  errorMessage: string | null = null;
  isLoading = false;
  stack: AgentEffectiveVoiceStack | null = null;

  private readonly api: ApiClient;
  private request: AbortController | null = null;

  constructor(api: ApiClient) {
    this.api = api;
    makeAutoObservable<this, "api" | "request">(
      this,
      { api: false, request: false },
      { autoBind: true },
    );
  }

  async load(organizationId: string, agentId: string): Promise<void> {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.errorMessage = null;
    this.isLoading = true;
    this.stack = null;

    try {
      const { data, response } = await this.api.GET(
        "/api/{organization_id}/agents/{agent_id}/effective-voice-stack",
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
        throw new Error("Agent effective voice stack request failed");
      }
      if (request.signal.aborted) {
        return;
      }
      runInAction(() => {
        this.stack = data;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.errorMessage = LOAD_ERROR_MESSAGE;
        });
      }
    } finally {
      if (this.request === request) {
        runInAction(() => {
          this.request = null;
          this.isLoading = false;
        });
      }
    }
  }

  clear(): void {
    this.request?.abort();
    this.request = null;
    this.errorMessage = null;
    this.isLoading = false;
    this.stack = null;
  }
}

export { AgentEffectiveVoiceStore };
