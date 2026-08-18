import createClient, { type Client, type Middleware } from "openapi-fetch";

import type { paths } from "@/api/generated/schema";

type ApiClient = Client<paths>;

interface ApiClientOptions {
  getAccessToken: () => string | null;
  onUnauthorized: () => void;
}

function createApiClient({
  getAccessToken,
  onUnauthorized,
}: ApiClientOptions): ApiClient {
  const client = createClient<paths>();
  const sessionMiddleware: Middleware = {
    onRequest({ request }) {
      const accessToken = getAccessToken();

      if (accessToken !== null) {
        request.headers.set("Authorization", `Bearer ${accessToken}`);
      }

      return request;
    },
    onResponse({ response }) {
      if (response.status === 401) {
        onUnauthorized();
      }

      return response;
    },
  };

  client.use(sessionMiddleware);
  return client;
}

export { createApiClient };
export type { ApiClient };
