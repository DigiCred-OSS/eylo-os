// hooks/useAgentIntegrations.ts
import type { TAgentToolsByIntegration } from "@eylo";
import { useEffect, useState } from "preact/hooks";
import { useAgentActions } from "./useActions";

/**
 * Hook to fetch and manage agent integrations
 */
export function useAgentIntegrations(agentId: string | undefined) {
  const { fetchAgentIntegrations } = useAgentActions();
  const [integrations, setIntegrations] = useState<TAgentToolsByIntegration[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!agentId) return;

    let cancelled = false;

    const fetchIntegrations = async () => {
      setLoading(true);
      setError(null);

      try {
        const data = await fetchAgentIntegrations(agentId);
        if (!cancelled) {
          setIntegrations(data as TAgentToolsByIntegration[]);
        }
      } catch (err) {
        if (!cancelled) {
          console.error(`Failed to fetch integrations for agent ${agentId}:`, err);
          setError(err instanceof Error ? err : new Error("Failed to fetch integrations"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchIntegrations();

    return () => {
      cancelled = true;
    };
  }, [agentId, fetchAgentIntegrations]);

  const integrationsWithData = integrations.filter((group) => group.integration);

  return {
    integrations: integrationsWithData,
    loading,
    error,
    hasIntegrations: integrationsWithData.length > 0,
  };
}
