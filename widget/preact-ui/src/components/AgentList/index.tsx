// components/AgentList/index.tsx
import { type FC } from "preact/compat";
import { useMemo, useState } from "preact/hooks";
import { FaExclamationTriangle, FaRobot } from "react-icons/fa";

import { PATHS } from "../../app";
import { useAgents } from "../../hooks/useEyloStore";
import { useBulkAgentIntegrations } from "../../hooks/useBulkAgentIntegrations";
import { useNavigate } from "../../library/MemoryRouter";
import type { TAgent, TAgentToolsByIntegration } from "@eylo";
import AgentIntegrationsModal from "../AgentIntegrationsModal";
import ChatWidgetContainer from "../ChatWidgetContainer";
import IntegrationBadge from "../IntegrationBadge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "../../design-system/components/Card";
import { Empty } from "../../design-system/components/Empty";
import { Skeleton } from "../../design-system/components/Skeleton";
import { Button } from "../../design-system/components/Button";
import { Stack } from "../../design-system/components/Stack";
import { Box } from "../../design-system/components/Box";
import { Flex } from "../../design-system/components/Flex";
import styles from "./AgentList.module.css";

// Subcomponent for individual agent card
const AgentCard: FC<{
  agent: TAgent;
  integrations: TAgentToolsByIntegration[];
  integrationsLoading: boolean;
  onStartConversation: (agentId: string) => void;
  onShowIntegrations: (agentId: string) => void;
}> = ({ agent, integrations, integrationsLoading, onStartConversation, onShowIntegrations }) => {
  const displayedIntegrations = integrations.slice(0, 3);
  const remainingCount = integrations.length - 3;
  const hasIntegrations = integrations.length > 0;

  return (
    <Card shadow="none" borderRadius="none" className={styles.agentCard}>
      <CardHeader className={styles.agentHeader}>
        <CardTitle className={styles.agentTitle}>{agent.name}</CardTitle>
        <CardDescription className={styles.agentDescription} title={agent.description || undefined}>
          {agent.description
            ? agent.description.length > 100
              ? `${agent.description.substring(0, 100)}...`
              : agent.description
            : "No description"}
        </CardDescription>
      </CardHeader>

      {(integrationsLoading || hasIntegrations) && (
        <CardContent className={styles.integrations}>
          {integrationsLoading ? (
            <Skeleton width="full" height="lg" />
          ) : (
            <Flex wrap="wrap" gap="xs">
              {displayedIntegrations.map((group) => (
                <IntegrationBadge
                  key={group.integration!.id}
                  integration={group.integration!}
                  onClick={() => onShowIntegrations(agent.id)}
                />
              ))}
              {remainingCount > 0 && (
                <Button variant="outline" size="sm" onClick={() => onShowIntegrations(agent.id)}>
                  +{remainingCount} more
                </Button>
              )}
            </Flex>
          )}
        </CardContent>
      )}

      <CardFooter className={styles.agentFooter}>
        <Button variant="ghost" size="sm" onClick={() => onStartConversation(agent.id)}>
          Start conversation
        </Button>
      </CardFooter>
    </Card>
  );
};

const AgentList: FC = () => {
  const navigate = useNavigate();
  const { agents, loading, error } = useAgents();

  // Single batch fetch for all agent integrations
  const agentIds = useMemo(() => agents.map((a) => a.id), [agents]);
  const { integrationsByAgent, loading: integrationsLoading } = useBulkAgentIntegrations(agentIds);

  // Modal state
  const [selectedAgent, setSelectedAgent] = useState<TAgent | null>(null);

  const handleStartConversation = (agentId: string) => {
    navigate(PATHS.CONVERSATION_WITH_AGENT, { id: agentId });
  };

  const handleShowIntegrations = (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId);
    if (agent) {
      setSelectedAgent(agent);
    }
  };

  const handleCloseModal = () => {
    setSelectedAgent(null);
  };

  return (
    <>
      <ChatWidgetContainer.ChatHeader
        title="Choose an agent"
        onBack={() => navigate(PATHS.CONVERSATION_LIST)}
      />
      <ChatWidgetContainer.ChatContent>
        <Box>
          <Stack>
            {/* Loading State */}
            {loading && (
              <Stack spacing="xs">
                <Skeleton height="4xl" width="full" />
                <Skeleton height="4xl" width="full" />
                <Skeleton height="4xl" width="full" />
              </Stack>
            )}

            {/* Error State */}
            {error && (
              <Empty
                icon={<FaExclamationTriangle aria-hidden="true" />}
                title="Error loading agents"
                description={error.message}
              />
            )}

            {/* Empty State */}
            {!loading && !error && agents.length === 0 && (
              <Empty
                icon={<FaRobot aria-hidden="true" />}
                title="No active agents"
                description="No agents are currently available"
              />
            )}

            {/* Agent List */}
            {!loading && !error && agents.length > 0 && (
              <Stack spacing="none">
                {agents.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    integrations={integrationsByAgent[agent.id] ?? []}
                    integrationsLoading={integrationsLoading}
                    onStartConversation={handleStartConversation}
                    onShowIntegrations={handleShowIntegrations}
                  />
                ))}
              </Stack>
            )}
          </Stack>
        </Box>
      </ChatWidgetContainer.ChatContent>

      {/* Integrations Modal */}
      {selectedAgent && (
        <AgentIntegrationsModal
          agentName={selectedAgent.name}
          agentId={selectedAgent.id}
          onClose={handleCloseModal}
        />
      )}
    </>
  );
};

export default AgentList;
