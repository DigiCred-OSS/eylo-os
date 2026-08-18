import type { ApiClient } from "@/api/client";
import type {
  AgentInputRequest,
  AgentRun,
  EventHealth,
  ExecutionBudget,
  ExecutionBudgetInput,
  OperationAgent,
  ServiceHealth,
  VoiceSession,
  VoiceSessionDetail,
} from "@/features/operations/operations.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class OperationsServiceError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "OperationsServiceError";
    this.status = status;
  }
}

class OperationsService {
  private readonly api: ApiClient;
  constructor(api: ApiClient) {
    this.api = api;
  }

  async listAgentRuns(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<AgentRun[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/agent-runs", {
        params: {
          path: { organization_id: organizationId },
          query: { limit: 100, offset: 0 },
        },
        signal,
      }),
      "Agent runs could not be loaded.",
    );
  }

  async agents(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<OperationAgent[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/agents", {
        params: {
          path: { organization_id: organizationId },
          query: {
            limit: 100,
            page: 1,
            sort_by: "name",
            sort_direction: "asc",
          },
        },
        signal,
      }),
      "Agent references could not be loaded.",
    ).data;
  }

  async getAgentRun(
    organizationId: string,
    runId: string,
    signal?: AbortSignal,
  ): Promise<AgentRun> {
    return requireData(
      await this.api.GET("/api/{organization_id}/agent-runs/{run_id}", {
        params: { path: { organization_id: organizationId, run_id: runId } },
        signal,
      }),
      "This Agent run could not be loaded.",
    );
  }

  async cancelAgentRun(
    organizationId: string,
    run: AgentRun,
  ): Promise<AgentRun> {
    return requireData(
      await this.api.POST("/api/{organization_id}/agent-runs/{run_id}/cancel", {
        params: { path: { organization_id: organizationId, run_id: run.id } },
        body: { expected_state_revision: run.state_revision },
      }),
      "The Agent run could not be cancelled.",
    ).run;
  }

  async answerAgentInput(
    organizationId: string,
    run: AgentRun,
    request: AgentInputRequest,
    response: unknown,
  ): Promise<AgentInputRequest> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/agent-runs/{run_id}/input-requests/{request_id}/response",
        {
          params: {
            path: {
              organization_id: organizationId,
              request_id: request.id,
              run_id: run.id,
            },
          },
          body: {
            expected_state_revision: request.state_revision,
            response: response as never,
          },
        },
      ),
      "The response could not be submitted.",
    );
  }

  async getBudget(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<ExecutionBudget | null> {
    const result = await this.api.GET(
      "/api/{organization_id}/agent-runs/budget",
      {
        params: { path: { organization_id: organizationId } },
        signal,
      },
    );
    if (result.response.status === 404) return null;
    return requireData(result, "Execution budget could not be loaded.");
  }

  async putBudget(
    organizationId: string,
    input: ExecutionBudgetInput,
  ): Promise<ExecutionBudget> {
    return requireData(
      await this.api.PUT("/api/{organization_id}/agent-runs/budget", {
        params: { path: { organization_id: organizationId } },
        body: input,
      }),
      "Execution budget could not be saved.",
    );
  }

  async listVoiceSessions(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<VoiceSession[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/voice-sessions", {
        params: {
          path: { organization_id: organizationId },
          query: { limit: 100, page: 1 },
        },
        signal,
      }),
      "Voice sessions could not be loaded.",
    ).data;
  }

  async getVoiceSession(
    organizationId: string,
    voiceSessionId: string,
    signal?: AbortSignal,
  ): Promise<VoiceSessionDetail> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/voice-sessions/{voice_session_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              voice_session_id: voiceSessionId,
            },
            query: { segment_limit: 200, segment_page: 1 },
          },
          signal,
        },
      ),
      "This voice session could not be loaded.",
    );
  }

  async eventHealth(signal?: AbortSignal): Promise<EventHealth> {
    return requireData(
      await this.api.GET("/api/events/health", { signal }),
      "Event health could not be loaded.",
    );
  }

  async serviceHealth(signal?: AbortSignal): Promise<ServiceHealth> {
    const started = performance.now();
    const result = await this.api.GET("/health", { signal });
    if (!result.response.ok)
      throw new OperationsServiceError(
        "The API health check failed.",
        result.response.status,
      );
    return {
      checkedAt: new Date().toISOString(),
      latencyMs: Math.round(performance.now() - started),
      online: true,
    };
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) return result.data;
  throw new OperationsServiceError(
    readDetail(result.error) ?? fallback,
    result.response.status,
  );
}

function readDetail(error: unknown): string | null {
  if (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    typeof error.detail === "string"
  )
    return error.detail;
  return null;
}

export { OperationsService, OperationsServiceError };
