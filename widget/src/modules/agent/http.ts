/**
 * HTTP utilities for agent-related API calls
 */

import {
  getServerBaseUrl,
  getWidgetApiPrefix,
  getWidgetHeaders,
  handleFetchError,
} from "@eylo/utils";

import type { TAgentToolsByIntegration } from "./types";

/**
 * Fetch agent tools grouped by integration with connection status
 *
 * @param organizationId - Organization ID
 * @param agentId - Agent ID
 * @param sessionId - Widget session ID for authentication
 * @returns Promise resolving to agent tools grouped by integration
 */
export async function fetchAgentToolsWithIntegrations(
  organizationId: string,
  agentId: string,
  sessionId: string
): Promise<TAgentToolsByIntegration[]> {
  const url = `${getServerBaseUrl()}${getWidgetApiPrefix(organizationId, "curated-connections")}/capabilities?agent_id=${encodeURIComponent(agentId)}`;
  const response = await fetch(url, {
    method: "GET",
    headers: getWidgetHeaders(sessionId),
  });
  if (!response.ok) {
    await handleFetchError(response, "fetch agent integration capabilities");
  }
  return (await response.json()) as TAgentToolsByIntegration[];
}

/**
 * Batch response for bulk agent tools with integrations
 */
export type TBulkAgentToolsByIntegration = {
  agentId: string;
  integrations: TAgentToolsByIntegration[];
};

type TBulkAgentToolsTransport = {
  agentId?: string;
  agent_id?: string;
  integrations: TAgentToolsByIntegration[];
};

/**
 * Fetch tools grouped by integration for multiple agents in one request.
 * Avoids N+1 API calls when rendering the agent list.
 */
export async function fetchBulkAgentToolsWithIntegrations(
  organizationId: string,
  agentIds: string[],
  sessionId: string
): Promise<TBulkAgentToolsByIntegration[]> {
  const url = `${getServerBaseUrl()}${getWidgetApiPrefix(organizationId, "curated-connections")}/bulk-capabilities`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...getWidgetHeaders(sessionId),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ agentIds }),
  });
  if (!response.ok) {
    await handleFetchError(response, "fetch agent integration capabilities");
  }
  return normalizeBulkAgentTools(
    (await response.json()) as TBulkAgentToolsTransport[]
  );
}

function normalizeBulkAgentTools(
  items: TBulkAgentToolsTransport[]
): TBulkAgentToolsByIntegration[] {
  return items.map((item) => {
    const agentId = item.agentId ?? item.agent_id;
    if (!agentId) {
      throw new Error("Agent tool response is missing an Agent ID.");
    }
    return { agentId, integrations: item.integrations };
  });
}
