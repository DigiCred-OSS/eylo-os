import type { ApiClient } from "@/api/client";
import type { Agent } from "@/features/agents/agents.types";
import type {
  Swarm,
  SwarmCreateInput,
  SwarmMember,
  SwarmRevision,
  SwarmUpdateInput,
} from "@/features/swarms/swarms.types";

class SwarmsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SwarmsServiceError";
    this.status = status;
  }
}

class SwarmsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listSwarms(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<Swarm[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/agent-swarm", {
        params: { path: { organization_id: organizationId } },
        signal,
      }),
      "Swarms could not be loaded.",
    );
  }

  async getSwarm(
    organizationId: string,
    swarmId: string,
    signal?: AbortSignal,
  ): Promise<Swarm> {
    const swarm = (await this.listSwarms(organizationId, signal)).find(
      (candidate) => candidate.id === swarmId,
    );
    if (swarm === undefined) {
      throw new SwarmsServiceError("This Swarm could not be found.", 404);
    }
    return swarm;
  }

  async createSwarm(
    organizationId: string,
    input: SwarmCreateInput,
  ): Promise<Swarm> {
    return requireData(
      await this.api.POST("/api/{organization_id}/agent-swarm/create", {
        body: input,
        params: { path: { organization_id: organizationId } },
      }),
      "The Swarm could not be created.",
    );
  }

  async updateSwarm(
    organizationId: string,
    swarmId: string,
    input: SwarmUpdateInput,
  ): Promise<Swarm> {
    return requireData(
      await this.api.PUT("/api/{organization_id}/agent-swarm/{swarm_id}", {
        body: input,
        params: {
          path: { organization_id: organizationId, swarm_id: swarmId },
        },
      }),
      "The Swarm could not be updated.",
    );
  }

  async deleteSwarm(organizationId: string, swarmId: string): Promise<void> {
    requireSuccess(
      await this.api.DELETE("/api/{organization_id}/agent-swarm/{swarm_id}", {
        params: {
          path: { organization_id: organizationId, swarm_id: swarmId },
        },
      }),
      "The Swarm could not be deleted.",
    );
  }

  async listMembers(
    organizationId: string,
    swarmId: string,
    signal?: AbortSignal,
  ): Promise<SwarmMember[]> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/agent-swarm/{swarm_id}/agents",
        {
          params: {
            path: { organization_id: organizationId, swarm_id: swarmId },
          },
          signal,
        },
      ),
      "Swarm members could not be loaded.",
    );
  }

  async listConversationalAgents(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<Agent[]> {
    const agents: Agent[] = [];
    let page = 1;
    let hasMore = true;
    while (hasMore) {
      const result = requireData(
        await this.api.GET("/api/{organization_id}/agents", {
          params: {
            path: { organization_id: organizationId },
            query: {
              kind: ["CONVERSATIONAL"],
              limit: 100,
              page,
              sort_by: "name",
              sort_direction: "asc",
            },
          },
          signal,
        }),
        "Conversational Agents could not be loaded.",
      );
      agents.push(...result.data);
      hasMore = result.hasMore === true;
      page += 1;
    }
    return agents;
  }

  async addMember(
    organizationId: string,
    swarmId: string,
    agentId: string,
    agentDescription: string | null,
    expectedDraftVersion: number,
  ): Promise<SwarmMember> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/agent-swarm/{swarm_id}/add-agent",
        {
          body: {
            agentDescription,
            agentId,
            expectedDraftVersion,
          },
          params: {
            path: { organization_id: organizationId, swarm_id: swarmId },
          },
        },
      ),
      "The Agent could not be added to this Swarm.",
    );
  }

  async removeMember(
    organizationId: string,
    swarmId: string,
    agentId: string,
    expectedDraftVersion: number,
  ): Promise<void> {
    requireSuccess(
      await this.api.DELETE(
        "/api/{organization_id}/agent-swarm/{swarm_id}/remove-agent",
        {
          body: { agentId, expectedDraftVersion },
          params: {
            path: { organization_id: organizationId, swarm_id: swarmId },
          },
        },
      ),
      "The Agent could not be removed from this Swarm.",
    );
  }

  async publish(
    organizationId: string,
    swarmId: string,
    expectedDraftVersion: number,
  ): Promise<SwarmRevision> {
    return requireData(
      await this.api.PUT(
        "/api/{organization_id}/agent-swarm/{swarm_id}/publish",
        {
          body: { expectedDraftVersion },
          params: {
            path: { organization_id: organizationId, swarm_id: swarmId },
          },
        },
      ),
      "The Swarm could not be published.",
    );
  }

  async withdraw(organizationId: string, swarmId: string): Promise<Swarm> {
    return requireData(
      await this.api.PUT(
        "/api/{organization_id}/agent-swarm/{swarm_id}/unpublish",
        {
          params: {
            path: { organization_id: organizationId, swarm_id: swarmId },
          },
        },
      ),
      "The Swarm could not be withdrawn.",
    );
  }

  async revoke(
    organizationId: string,
    swarmId: string,
    revision: number,
    reason: string,
  ): Promise<SwarmRevision> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/agent-swarm/{swarm_id}/revisions/revoke",
        {
          body: { reason, revision },
          params: {
            path: { organization_id: organizationId, swarm_id: swarmId },
          },
        },
      ),
      "The Swarm revision could not be revoked.",
    );
  }
}

function requireData<Data>(
  result: { data?: Data; error?: unknown; response: Response },
  fallback: string,
): Data {
  if (result.response.ok && result.data !== undefined) return result.data;
  throw serviceError(result.error, result.response.status, fallback);
}

function requireSuccess(
  result: { error?: unknown; response: Response },
  fallback: string,
): void {
  if (result.response.ok) return;
  throw serviceError(result.error, result.response.status, fallback);
}

function serviceError(
  error: unknown,
  status: number,
  fallback: string,
): SwarmsServiceError {
  if (!isRecord(error)) return new SwarmsServiceError(fallback, status);
  if (typeof error.detail === "string") {
    return new SwarmsServiceError(error.detail, status);
  }
  if (Array.isArray(error.detail)) {
    const messages = error.detail
      .map((item) =>
        isRecord(item) && typeof item.msg === "string" ? item.msg : null,
      )
      .filter((message): message is string => message !== null);
    if (messages.length > 0) {
      return new SwarmsServiceError(messages.join(" "), status);
    }
  }
  return new SwarmsServiceError(fallback, status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { SwarmsService, SwarmsServiceError };
