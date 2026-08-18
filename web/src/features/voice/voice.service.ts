import type { ApiClient } from "@/api/client";
import type {
  VoiceConfigCompatibility,
  VoiceConfigCreateInput,
  VoiceConfigRecord,
  VoiceConfigUpdateInput,
} from "@/features/voice/voice.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class VoiceConfigServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "VoiceConfigServiceError";
    this.status = status;
  }
}

class VoiceConfigService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async list(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<VoiceConfigRecord[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/voice-configs", {
        params: { path: { organization_id: organizationId } },
        signal,
      }),
      "Voice Configs could not be loaded.",
    );
  }

  async get(
    organizationId: string,
    voiceConfigId: string,
    signal?: AbortSignal,
  ): Promise<VoiceConfigRecord> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/voice-configs/{voice_config_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              voice_config_id: voiceConfigId,
            },
          },
          signal,
        },
      ),
      "This Voice Config could not be loaded.",
    );
  }

  async getCompatibility(
    organizationId: string,
    voiceConfigId: string,
    signal?: AbortSignal,
  ): Promise<VoiceConfigCompatibility> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/voice-configs/{voice_config_id}/compatibility",
        {
          params: {
            path: {
              organization_id: organizationId,
              voice_config_id: voiceConfigId,
            },
          },
          signal,
        },
      ),
      "Voice capability details could not be loaded.",
    );
  }

  async create(
    organizationId: string,
    input: VoiceConfigCreateInput,
  ): Promise<VoiceConfigRecord> {
    return requireData(
      await this.api.POST("/api/{organization_id}/voice-configs", {
        body: input,
        params: { path: { organization_id: organizationId } },
      }),
      "The Voice Config could not be created.",
    );
  }

  async update(
    organizationId: string,
    voiceConfigId: string,
    input: VoiceConfigUpdateInput,
  ): Promise<VoiceConfigRecord> {
    return requireData(
      await this.api.PATCH(
        "/api/{organization_id}/voice-configs/{voice_config_id}",
        {
          body: input,
          params: {
            path: {
              organization_id: organizationId,
              voice_config_id: voiceConfigId,
            },
          },
        },
      ),
      "The Voice Config could not be updated.",
    );
  }

  async delete(organizationId: string, voiceConfigId: string): Promise<void> {
    requireSuccess(
      await this.api.DELETE(
        "/api/{organization_id}/voice-configs/{voice_config_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              voice_config_id: voiceConfigId,
            },
          },
        },
      ),
      "The Voice Config could not be deleted.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) {
    return result.data;
  }
  throw serviceError(result, fallback);
}

function requireSuccess(result: ApiResult<unknown>, fallback: string): void {
  if (result.response.ok) {
    return;
  }
  throw serviceError(result, fallback);
}

function serviceError(
  result: ApiResult<unknown>,
  fallback: string,
): VoiceConfigServiceError {
  return new VoiceConfigServiceError(
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

export { VoiceConfigService, VoiceConfigServiceError };
