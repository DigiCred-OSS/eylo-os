import type { ApiClient } from "@/api/client";
import type {
  ScheduleAgent,
  ScheduleCreateInput,
  ScheduleRecord,
  ScheduleRun,
  ScheduleUpdateInput,
} from "@/features/automations/automations.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class AutomationsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AutomationsServiceError";
    this.status = status;
  }
}

class AutomationsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async list(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<ScheduleRecord[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/schedules", {
        params: { path: { organization_id: organizationId } },
        signal,
      }),
      "Automations could not be loaded.",
    );
  }

  async actions(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<string[]> {
    const data = requireData(
      await this.api.GET("/api/{organization_id}/schedules/actions", {
        params: { path: { organization_id: organizationId } },
        signal,
      }),
      "Schedule actions could not be loaded.",
    );
    if (
      typeof data !== "object" ||
      data === null ||
      !("actions" in data) ||
      !Array.isArray(data.actions) ||
      !data.actions.every((action) => typeof action === "string")
    ) {
      throw new AutomationsServiceError(
        "The schedule action catalog is invalid.",
        502,
      );
    }
    return data.actions;
  }

  async agents(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<ScheduleAgent[]> {
    const page = requireData(
      await this.api.GET("/api/{organization_id}/agents", {
        params: {
          path: { organization_id: organizationId },
          query: {
            limit: 100,
            page: 1,
            sort_by: "name",
            sort_direction: "asc",
            status: ["ACTIVE"],
          },
        },
        signal,
      }),
      "Published Agents could not be loaded.",
    );
    return page.data.filter((agent) => agent.publishedRevision != null);
  }

  async get(
    organizationId: string,
    scheduleId: string,
    signal?: AbortSignal,
  ): Promise<ScheduleRecord> {
    return requireData(
      await this.api.GET("/api/{organization_id}/schedules/{schedule_id}", {
        params: {
          path: { organization_id: organizationId, schedule_id: scheduleId },
        },
        signal,
      }),
      "This automation could not be loaded.",
    );
  }

  async runs(
    organizationId: string,
    scheduleId: string,
    signal?: AbortSignal,
  ): Promise<ScheduleRun[]> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/schedules/{schedule_id}/runs",
        {
          params: {
            path: { organization_id: organizationId, schedule_id: scheduleId },
          },
          signal,
        },
      ),
      "Automation runs could not be loaded.",
    );
  }

  async create(
    organizationId: string,
    input: ScheduleCreateInput,
  ): Promise<ScheduleRecord> {
    return requireData(
      await this.api.POST("/api/{organization_id}/schedules", {
        params: { path: { organization_id: organizationId } },
        body: input,
      }),
      "The automation could not be created.",
    );
  }

  async update(
    organizationId: string,
    scheduleId: string,
    input: ScheduleUpdateInput,
  ): Promise<ScheduleRecord> {
    return requireData(
      await this.api.PUT("/api/{organization_id}/schedules/{schedule_id}", {
        params: {
          path: { organization_id: organizationId, schedule_id: scheduleId },
        },
        body: input,
      }),
      "The automation could not be updated.",
    );
  }

  async cancel(organizationId: string, scheduleId: string): Promise<void> {
    requireOk(
      await this.api.DELETE("/api/{organization_id}/schedules/{schedule_id}", {
        params: {
          path: { organization_id: organizationId, schedule_id: scheduleId },
        },
      }),
      "The automation could not be retired.",
    );
  }

  async revoke(
    organizationId: string,
    schedule: ScheduleRecord,
    reason: string,
  ): Promise<void> {
    requireOk(
      await this.api.POST(
        "/api/{organization_id}/schedules/{schedule_id}/revisions/{revision}/revoke",
        {
          params: {
            path: {
              organization_id: organizationId,
              revision: schedule.published_revision,
              schedule_id: schedule.id,
            },
          },
          body: { reason },
        },
      ),
      "The automation revision could not be revoked.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) return result.data;
  throw new AutomationsServiceError(
    readDetail(result.error) ?? fallback,
    result.response.status,
  );
}

function requireOk(result: ApiResult<unknown>, fallback: string): void {
  if (result.response.ok) return;
  throw new AutomationsServiceError(
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
  ) {
    return error.detail;
  }
  return null;
}

export { AutomationsService, AutomationsServiceError };
