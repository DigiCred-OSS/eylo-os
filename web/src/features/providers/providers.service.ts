import type { components } from "@/api/generated/schema";
import type { ApiClient } from "@/api/client";
import type {
  ProviderCapabilities,
  ProviderCapability,
  ProviderCatalog,
  ProviderConfigCreateInput,
  ProviderConfigRecord,
  ProviderConfigResponse,
  ProviderConfigUpdateInput,
  ProviderTool,
} from "@/features/providers/providers.types";

const REQUEST_ERROR_MESSAGE =
  "The provider configuration request failed. Review the values and try again.";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class ProviderServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ProviderServiceError";
    this.status = status;
  }
}

class ProvidersService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async loadCatalog(): Promise<ProviderCatalog> {
    return requireData(
      await this.api.GET("/api/provider-onboarding/catalog"),
      "Provider setup information could not be loaded.",
    );
  }

  async loadCapabilities(): Promise<ProviderCapabilities> {
    return requireData(
      await this.api.GET("/api/capabilities"),
      "Provider readiness could not be loaded.",
    );
  }

  async list(capability: ProviderCapability): Promise<ProviderConfigRecord[]> {
    const data = await this.listRaw(capability);
    return data.map((config) => normalizeConfig(capability, config));
  }

  async listProviderTools(
    organizationId: string,
    capability: ProviderCapability,
  ): Promise<ProviderTool[]> {
    const data = requireData(
      await this.api.GET("/api/{organization_id}/tools/provider-catalog", {
        params: {
          path: { organization_id: organizationId },
          query: { capability },
        },
      }),
      "Agent tools for this provider could not be loaded.",
    );
    return data.items;
  }

  async get(
    capability: ProviderCapability,
    configId: string,
  ): Promise<ProviderConfigRecord> {
    const data = await this.getRaw(capability, configId);
    return normalizeConfig(capability, data);
  }

  async create(
    capability: ProviderCapability,
    input: ProviderConfigCreateInput,
  ): Promise<ProviderConfigRecord> {
    const data = await this.createRaw(capability, input);
    return normalizeConfig(capability, data);
  }

  async update(
    capability: ProviderCapability,
    configId: string,
    input: ProviderConfigUpdateInput,
  ): Promise<ProviderConfigRecord> {
    const data = await this.updateRaw(capability, configId, input);
    return normalizeConfig(capability, data);
  }

  async verify(
    capability: ProviderCapability,
    configId: string,
  ): Promise<void> {
    switch (capability) {
      case "llm":
        requireData(
          await this.api.POST("/api/llm-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "stt":
        requireData(
          await this.api.POST("/api/stt-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "tts":
        requireData(
          await this.api.POST("/api/tts-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "realtime":
        requireData(
          await this.api.POST("/api/realtime-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "webrtc":
        requireData(
          await this.api.POST("/api/webrtc-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "telephony":
        requireData(
          await this.api.POST("/api/telephony-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "email":
        requireData(
          await this.api.POST("/api/email-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "storage":
        requireData(
          await this.api.POST("/api/storage-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "embedding":
        requireData(
          await this.api.POST("/api/embedding-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "reranking":
        requireData(
          await this.api.POST("/api/reranking-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "memory":
        requireData(
          await this.api.POST("/api/memory-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      case "sandbox":
        requireData(
          await this.api.POST("/api/sandbox-configs/{config_id}/verify", {
            params: { path: { config_id: configId } },
          }),
        );
        return;
      default:
        assertNever(capability);
    }
  }

  async delete(
    capability: ProviderCapability,
    configId: string,
  ): Promise<void> {
    let result: ApiResult<unknown>;

    switch (capability) {
      case "llm":
        result = await this.api.DELETE("/api/llm-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "stt":
        result = await this.api.DELETE("/api/stt-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "tts":
        result = await this.api.DELETE("/api/tts-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "realtime":
        result = await this.api.DELETE("/api/realtime-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "webrtc":
        result = await this.api.DELETE("/api/webrtc-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "telephony":
        result = await this.api.DELETE("/api/telephony-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "email":
        result = await this.api.DELETE("/api/email-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "storage":
        result = await this.api.DELETE("/api/storage-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "embedding":
        result = await this.api.DELETE("/api/embedding-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "reranking":
        result = await this.api.DELETE("/api/reranking-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "memory":
        result = await this.api.DELETE("/api/memory-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      case "sandbox":
        result = await this.api.DELETE("/api/sandbox-configs/{config_id}", {
          params: { path: { config_id: configId } },
        });
        break;
      default:
        return assertNever(capability);
    }

    requireSuccess(result);
  }

  private async listRaw(
    capability: ProviderCapability,
  ): Promise<ProviderConfigResponse[]> {
    switch (capability) {
      case "llm":
        return requireData(await this.api.GET("/api/llm-configs"));
      case "stt":
        return requireData(await this.api.GET("/api/stt-configs"));
      case "tts":
        return requireData(await this.api.GET("/api/tts-configs"));
      case "realtime":
        return requireData(await this.api.GET("/api/realtime-configs"));
      case "webrtc":
        return requireData(await this.api.GET("/api/webrtc-configs"));
      case "telephony":
        return requireData(await this.api.GET("/api/telephony-configs"));
      case "email":
        return requireData(await this.api.GET("/api/email-configs"));
      case "storage":
        return requireData(await this.api.GET("/api/storage-configs"));
      case "embedding":
        return requireData(await this.api.GET("/api/embedding-configs"));
      case "reranking":
        return requireData(await this.api.GET("/api/reranking-configs"));
      case "memory":
        return requireData(await this.api.GET("/api/memory-configs"));
      case "sandbox":
        return requireData(await this.api.GET("/api/sandbox-configs"));
      default:
        return assertNever(capability);
    }
  }

  private async getRaw(
    capability: ProviderCapability,
    configId: string,
  ): Promise<ProviderConfigResponse> {
    const params = { params: { path: { config_id: configId } } };

    switch (capability) {
      case "llm":
        return requireData(
          await this.api.GET("/api/llm-configs/{config_id}", params),
        );
      case "stt":
        return requireData(
          await this.api.GET("/api/stt-configs/{config_id}", params),
        );
      case "tts":
        return requireData(
          await this.api.GET("/api/tts-configs/{config_id}", params),
        );
      case "realtime":
        return requireData(
          await this.api.GET("/api/realtime-configs/{config_id}", params),
        );
      case "webrtc":
        return requireData(
          await this.api.GET("/api/webrtc-configs/{config_id}", params),
        );
      case "telephony":
        return requireData(
          await this.api.GET("/api/telephony-configs/{config_id}", params),
        );
      case "email":
        return requireData(
          await this.api.GET("/api/email-configs/{config_id}", params),
        );
      case "storage":
        return requireData(
          await this.api.GET("/api/storage-configs/{config_id}", params),
        );
      case "embedding":
        return requireData(
          await this.api.GET("/api/embedding-configs/{config_id}", params),
        );
      case "reranking":
        return requireData(
          await this.api.GET("/api/reranking-configs/{config_id}", params),
        );
      case "memory":
        return requireData(
          await this.api.GET("/api/memory-configs/{config_id}", params),
        );
      case "sandbox":
        return requireData(
          await this.api.GET("/api/sandbox-configs/{config_id}", params),
        );
      default:
        return assertNever(capability);
    }
  }

  private async createRaw(
    capability: ProviderCapability,
    input: ProviderConfigCreateInput,
  ): Promise<ProviderConfigResponse> {
    switch (capability) {
      case "llm":
        return requireData(
          await this.api.POST("/api/llm-configs", {
            body: input as components["schemas"]["LLMConfigCreate"],
          }),
        );
      case "stt":
        return requireData(
          await this.api.POST("/api/stt-configs", {
            body: input as components["schemas"]["VoiceConfigCreate"],
          }),
        );
      case "tts":
        return requireData(
          await this.api.POST("/api/tts-configs", {
            body: input as components["schemas"]["VoiceConfigCreate"],
          }),
        );
      case "realtime":
        return requireData(
          await this.api.POST("/api/realtime-configs", {
            body: input as components["schemas"]["VoiceConfigCreate"],
          }),
        );
      case "webrtc":
        return requireData(
          await this.api.POST("/api/webrtc-configs", {
            body: input as components["schemas"]["WebRTCConfigCreate"],
          }),
        );
      case "telephony":
        return requireData(
          await this.api.POST("/api/telephony-configs", {
            body: input as components["schemas"]["ProviderConfigCreateSchema"],
          }),
        );
      case "email":
        return requireData(
          await this.api.POST("/api/email-configs", {
            body: input as components["schemas"]["EmailConfigCreate"],
          }),
        );
      case "storage":
        return requireData(
          await this.api.POST("/api/storage-configs", {
            body: input as components["schemas"]["StorageConfigCreate"],
          }),
        );
      case "embedding":
        return requireData(
          await this.api.POST("/api/embedding-configs", {
            body: input as components["schemas"]["EmbeddingConfigCreate"],
          }),
        );
      case "reranking":
        return requireData(
          await this.api.POST("/api/reranking-configs", {
            body: input as components["schemas"]["RerankingConfigCreate"],
          }),
        );
      case "memory":
        return requireData(
          await this.api.POST("/api/memory-configs", {
            body: input as components["schemas"]["MemoryConfigCreate"],
          }),
        );
      case "sandbox":
        return requireData(
          await this.api.POST("/api/sandbox-configs", {
            body: input as components["schemas"]["SandboxConfigCreate"],
          }),
        );
      default:
        return assertNever(capability);
    }
  }

  private async updateRaw(
    capability: ProviderCapability,
    configId: string,
    input: ProviderConfigUpdateInput,
  ): Promise<ProviderConfigResponse> {
    const params = { params: { path: { config_id: configId } } };

    switch (capability) {
      case "llm":
        return requireData(
          await this.api.PATCH("/api/llm-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["LLMConfigUpdate"],
          }),
        );
      case "stt":
        return requireData(
          await this.api.PATCH("/api/stt-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["VoiceConfigUpdate"],
          }),
        );
      case "tts":
        return requireData(
          await this.api.PATCH("/api/tts-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["VoiceConfigUpdate"],
          }),
        );
      case "realtime":
        return requireData(
          await this.api.PATCH("/api/realtime-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["VoiceConfigUpdate"],
          }),
        );
      case "webrtc":
        return requireData(
          await this.api.PATCH("/api/webrtc-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["WebRTCConfigUpdate"],
          }),
        );
      case "telephony":
        return requireData(
          await this.api.PATCH("/api/telephony-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["ProviderConfigUpdateSchema"],
          }),
        );
      case "email":
        return requireData(
          await this.api.PATCH("/api/email-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["EmailConfigUpdate"],
          }),
        );
      case "storage":
        return requireData(
          await this.api.PATCH("/api/storage-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["StorageConfigUpdate"],
          }),
        );
      case "embedding":
        return requireData(
          await this.api.PATCH("/api/embedding-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["EmbeddingConfigUpdate"],
          }),
        );
      case "reranking":
        return requireData(
          await this.api.PATCH("/api/reranking-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["RerankingConfigUpdate"],
          }),
        );
      case "memory":
        return requireData(
          await this.api.PATCH("/api/memory-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["MemoryConfigUpdate"],
          }),
        );
      case "sandbox":
        return requireData(
          await this.api.PATCH("/api/sandbox-configs/{config_id}", {
            ...params,
            body: input as components["schemas"]["SandboxConfigUpdate"],
          }),
        );
      default:
        return assertNever(capability);
    }
  }
}

function normalizeConfig(
  capability: ProviderCapability,
  raw: ProviderConfigResponse,
): ProviderConfigRecord {
  return {
    capability,
    config: raw.config,
    configured: raw.configured,
    enabled: raw.enabled,
    id: raw.id,
    name: raw.name,
    provider: raw.provider,
    raw,
    ready: raw.ready,
    revision: raw.revision,
    secrets: raw.secrets,
    verified: raw.verified,
    verifiedAt: raw.verifiedAt,
  };
}

function requireData<Data>(
  result: ApiResult<Data>,
  fallback = REQUEST_ERROR_MESSAGE,
): Data {
  if (!result.response.ok || result.data === undefined) {
    throw new ProviderServiceError(
      getSafeErrorMessage(result.error, fallback),
      result.response.status,
    );
  }
  return result.data;
}

function requireSuccess(
  result: ApiResult<unknown>,
  fallback = REQUEST_ERROR_MESSAGE,
): void {
  if (!result.response.ok) {
    throw new ProviderServiceError(
      getSafeErrorMessage(result.error, fallback),
      result.response.status,
    );
  }
}

function getSafeErrorMessage(error: unknown, fallback: string): string {
  if (typeof error !== "object" || error === null || !("detail" in error)) {
    return fallback;
  }

  const detail = error.detail;
  if (typeof detail === "string" && detail.trim() !== "") {
    return detail.slice(0, 500);
  }
  if (!Array.isArray(detail)) {
    return fallback;
  }

  const messages = detail.flatMap((item) => {
    if (
      typeof item !== "object" ||
      item === null ||
      !("msg" in item) ||
      typeof item.msg !== "string"
    ) {
      return [];
    }
    return [item.msg];
  });
  return messages.length > 0 ? messages.join(" ").slice(0, 500) : fallback;
}

function assertNever(value: never): never {
  throw new Error(`Unsupported provider capability: ${String(value)}`);
}

export { ProviderServiceError, ProvidersService };
