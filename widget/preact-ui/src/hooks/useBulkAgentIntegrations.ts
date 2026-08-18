// hooks/useBulkAgentIntegrations.ts
import type { TAgentToolsByIntegration } from "@eylo";
import { useEffect, useState } from "preact/hooks";
import { useAgentActions } from "./useActions";

/**
 * Hook to fetch integrations for multiple agents in a single API call.
 * Replaces per-agent useAgentIntegrations to avoid N+1 requests on the agent list.
 */
export function useBulkAgentIntegrations(agentIds: string[]) {
  const { fetchBulkAgentIntegrations } = useAgentActions();
  const [integrationsByAgent, setIntegrationsByAgent] = useState<
    Record<string, TAgentToolsByIntegration[]>
  >({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Stable key to detect when agent IDs actually change
  const idsKey = agentIds.join(",");

  useEffect(() => {
    if (agentIds.length === 0) return;

    let cancelled = false;

    const fetchAll = async () => {
      setLoading(true);
      setError(null);

      try {
        const results = await fetchBulkAgentIntegrations(agentIds);
        if (!cancelled) {
          const map: Record<string, TAgentToolsByIntegration[]> = {};
          for (const item of results) {
            map[item.agentId] = (item.integrations ?? []).filter(
              (g: TAgentToolsByIntegration) => g.integration
            );
          }
          setIntegrationsByAgent(map);
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to fetch bulk agent integrations:", err);
          setError(err instanceof Error ? err : new Error("Failed to fetch integrations"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchAll();

    return () => {
      cancelled = true;
    };
  }, [idsKey, fetchBulkAgentIntegrations]);

  return { integrationsByAgent, loading, error };
}
