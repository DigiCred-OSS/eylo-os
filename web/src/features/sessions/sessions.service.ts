import type { ApiClient } from "@/api/client";
import { toUserSessionListApiQuery } from "@/features/sessions/sessions.query";
import {
  SESSION_TIMELINE_PAGE_SIZE,
  type SessionCollectionQuery,
  type SessionTimelinePage,
  type SessionTimelineQuery,
  type UserSession,
  type UserSessionPage,
} from "@/features/sessions/sessions.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class SessionsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SessionsServiceError";
    this.status = status;
  }
}

class SessionsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async list(
    organizationId: string,
    query: SessionCollectionQuery,
    signal?: AbortSignal,
  ): Promise<UserSessionPage> {
    return requireData(
      await this.api.GET("/api/{organization_id}/sessions", {
        params: {
          path: { organization_id: organizationId },
          query: toUserSessionListApiQuery(query),
        },
        signal,
      }),
      "Sessions could not be loaded.",
    );
  }

  async get(
    organizationId: string,
    userSessionId: string,
    signal?: AbortSignal,
  ): Promise<UserSession> {
    return requireData(
      await this.api.GET("/api/{organization_id}/sessions/{user_session_id}", {
        params: {
          path: {
            organization_id: organizationId,
            user_session_id: userSessionId,
          },
        },
        signal,
      }),
      "This session could not be loaded.",
    );
  }

  async timeline(
    organizationId: string,
    userSessionId: string,
    query: SessionTimelineQuery,
    page: number,
    signal?: AbortSignal,
  ): Promise<SessionTimelinePage> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/sessions/{user_session_id}/timeline",
        {
          params: {
            path: {
              organization_id: organizationId,
              user_session_id: userSessionId,
            },
            query: {
              category:
                query.categories.length === 0 ? undefined : query.categories,
              include_technical: query.includeTechnical,
              limit: SESSION_TIMELINE_PAGE_SIZE,
              page,
            },
          },
          signal,
        },
      ),
      "The session timeline could not be loaded.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) {
    return result.data;
  }
  throw new SessionsServiceError(
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

export { SessionsService, SessionsServiceError };
