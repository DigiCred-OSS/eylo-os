import type { ApiClient } from "@/api/client";
import type {
  AvailableNumber,
  AvailableNumberSearch,
  DeletionJob,
  NumberPurchase,
  PhoneNumber,
  PhoneNumberCreate,
  PhoneNumberUpdate,
  TelephonyAgent,
  TelephonyCall,
  TelephonyConfig,
} from "@/features/telephony/telephony.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class TelephonyServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "TelephonyServiceError";
    this.status = status;
  }
}

class TelephonyService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listPhoneNumbers(signal?: AbortSignal): Promise<PhoneNumber[]> {
    const page = requireData(
      await this.api.GET("/api/phone-numbers", {
        params: { query: { limit: 100, page: 1 } },
        signal,
      }),
      "Phone numbers could not be loaded.",
    );
    return page.data;
  }

  async getPhoneNumber(id: string, signal?: AbortSignal): Promise<PhoneNumber> {
    return requireData(
      await this.api.GET("/api/phone-numbers/{phone_number_id}", {
        params: { path: { phone_number_id: id } },
        signal,
      }),
      "This phone number could not be loaded.",
    );
  }

  async registerPhoneNumber(input: PhoneNumberCreate): Promise<PhoneNumber> {
    return requireData(
      await this.api.POST("/api/phone-numbers", { body: input }),
      "The phone number could not be registered.",
    );
  }

  async updatePhoneNumber(
    id: string,
    input: PhoneNumberUpdate,
  ): Promise<PhoneNumber> {
    return requireData(
      await this.api.PATCH("/api/phone-numbers/{phone_number_id}", {
        params: { path: { phone_number_id: id } },
        body: input,
      }),
      "The phone number could not be updated.",
    );
  }

  async deletePhoneNumber(id: string): Promise<PhoneNumber> {
    return requireData(
      await this.api.DELETE("/api/phone-numbers/{phone_number_id}", {
        params: { path: { phone_number_id: id } },
      }),
      "The phone number could not be removed from Eylo.",
    );
  }

  async listConfigs(signal?: AbortSignal): Promise<TelephonyConfig[]> {
    return requireData(
      await this.api.GET("/api/telephony-configs", { signal }),
      "Telephony configurations could not be loaded.",
    );
  }

  async listAgents(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<TelephonyAgent[]> {
    const result = requireData(
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
    );
    return result.data;
  }

  async searchAvailableNumbers(
    configId: string,
    search: AvailableNumberSearch,
    signal?: AbortSignal,
  ): Promise<AvailableNumber[]> {
    const result = requireData(
      await this.api.GET(
        "/api/telephony-configs/{provider_config_id}/numbers/available",
        {
          params: {
            path: { provider_config_id: configId },
            query: {
              areaCode: search.areaCode || null,
              contains: search.contains || null,
              country: search.country,
              limit: search.limit,
              numberType: search.numberType,
            },
          },
          signal,
        },
      ),
      "Available numbers could not be searched.",
    );
    return result.numbers;
  }

  async purchaseNumber(
    configId: string,
    input: NumberPurchase,
    idempotencyKey: string,
  ): Promise<PhoneNumber> {
    return requireData(
      await this.api.POST(
        "/api/telephony-configs/{provider_config_id}/numbers/purchase",
        {
          params: {
            header: { "Idempotency-Key": idempotencyKey },
            path: { provider_config_id: configId },
          },
          body: input,
        },
      ),
      "The carrier did not complete the phone-number purchase.",
    );
  }

  async listCalls(signal?: AbortSignal): Promise<TelephonyCall[]> {
    const page = requireData(
      await this.api.GET("/api/calls", {
        params: { query: { limit: 100, page: 1 } },
        signal,
      }),
      "Calls could not be loaded.",
    );
    return page.data;
  }

  async getCall(id: string, signal?: AbortSignal): Promise<TelephonyCall> {
    return requireData(
      await this.api.GET("/api/calls/{call_id}", {
        params: { path: { call_id: id } },
        signal,
      }),
      "This call could not be loaded.",
    );
  }

  async deleteCall(id: string): Promise<DeletionJob> {
    return requireData(
      await this.api.DELETE("/api/calls/{call_id}", {
        params: { path: { call_id: id } },
      }),
      "Call deletion could not be requested.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) return result.data;
  throw new TelephonyServiceError(
    readDetail(result.error) ?? fallback,
    result.response.status,
  );
}

function readDetail(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

export { TelephonyService, TelephonyServiceError };
