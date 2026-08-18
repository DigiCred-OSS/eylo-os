import { Fragment } from "preact";
import { type FC } from "preact/compat";
import { useEffect, useMemo } from "preact/hooks";
import { useAgentIntegrations } from "../../hooks/useAgentIntegrations";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
} from "../../design-system/components/Sheet";
import { Badge } from "../../design-system/components/Badge";
import { Text } from "../../design-system/components/Typography";
import { Button } from "../../design-system/components/Button";
import { Empty } from "../../design-system/components/Empty";
import { Skeleton } from "../../design-system/components/Skeleton";
import { List, ListItem } from "../../design-system/components/List";
import { Stack } from "../../design-system/components/Stack";
import { Box } from "../../design-system/components/Box";
import { Flex } from "../../design-system/components/Flex";
import styles from "./AgentIntegrationsModal.module.css";
import { Separator } from "../../design-system";

interface AgentIntegrationsModalProps {
  agentName: string;
  agentId: string;
  onClose: () => void;
}

interface IntegrationDisplay {
  id: string;
  displayName: string;
  iconUrl: string | null;
  iconLetter: string;
  connectionKind: "ORGANIZATION" | "CONTACT";
  hasActiveConnection: boolean;
  tools: Array<{
    id: string;
    displayName: string;
    description: string;
  }>;
}

const IntegrationHeader: FC<{ integration: IntegrationDisplay }> = ({ integration }) => (
  <Box padding="sm" borderRadius="sm" background="muted-subtle">
    <Flex align="center" gap="sm">
      <Flex align="center" gap="xs" grow>
        {integration.iconUrl ? (
          <Box display="inline-flex" width="md" height="md" borderRadius="sm">
            <img
              src={integration.iconUrl}
              alt={`${integration.displayName} icon`}
              className="ew-object-contain"
              style={{ width: "100%", height: "100%" }}
            />
          </Box>
        ) : (
          <Box
            width="md"
            height="md"
            borderRadius="sm"
            background="primary"
            color="primary-foreground"
          >
            <Flex align="center" justify="center" height="full">
              <Text as="span" size="xs" semibold>
                {integration.iconLetter}
              </Text>
            </Flex>
          </Box>
        )}
        <Text size="small" semibold>
          {integration.displayName}
        </Text>
      </Flex>

      <Badge variant="outline">
        {integration.connectionKind === "ORGANIZATION" ? "🏢 Organization" : "👤 Personal"}
      </Badge>

      <Badge variant={integration.hasActiveConnection ? "success" : "destructive"}>
        {integration.hasActiveConnection
          ? "Connected"
          : integration.connectionKind === "ORGANIZATION"
            ? "Requires Admin"
            : "Not Connected"}
      </Badge>
    </Flex>
  </Box>
);

const ToolsList: FC<{ tools: IntegrationDisplay["tools"] }> = ({ tools }) => (
  <List variant="compact">
    {tools.map((tool) => (
      <ListItem key={tool.id} label={tool.displayName} description={tool.description} />
    ))}
  </List>
);

const AgentIntegrationsModal: FC<AgentIntegrationsModalProps> = ({
  agentName,
  agentId,
  onClose,
}) => {
  // Fetch integrations using our hook
  const { integrations, loading, error } = useAgentIntegrations(agentId);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  // Transform data into display format
  const displayData = useMemo(() => {
    const integrationsWithTools = integrations.filter(
      (group) => group.integration !== null && group.tools.length > 0
    );

    const integrationDisplays: IntegrationDisplay[] = integrationsWithTools.map((group) => {
      const integration = group.integration!;
      const displayName = integration.displayName || integration.name;
      const connectionKind = (integration.connectionKind || "ORGANIZATION") as
        | "ORGANIZATION"
        | "CONTACT";

      return {
        id: integration.id,
        displayName,
        iconUrl: integration.iconUrl ?? null,
        iconLetter: displayName.charAt(0).toUpperCase(),
        connectionKind,
        hasActiveConnection: integration.hasActiveConnection,
        tools: group.tools.map((tool) => ({
          id: tool.id,
          displayName: tool.displayName,
          description: tool.description,
        })),
      };
    });

    const totalTools = integrationDisplays.reduce(
      (sum, integration) => sum + integration.tools.length,
      0
    );

    const orgCount = integrationDisplays.filter(
      (integration) => integration.connectionKind === "ORGANIZATION"
    ).length;

    const personalCount = integrationDisplays.filter(
      (integration) => integration.connectionKind === "CONTACT"
    ).length;

    return {
      integrations: integrationDisplays,
      totalTools,
      orgCount,
      personalCount,
    };
  }, [integrations]);

  return (
    <Sheet open>
      <SheetContent
        className={styles.dialogContent}
        dismissible={true}
        onToggle={onClose}
        shadow="md"
      >
        <SheetHeader>
          <SheetTitle>{agentName} Capabilities</SheetTitle>
          <Box marginTop="xs">
            <Stack spacing="xs">
              {loading && <Text size="small">Loading integrations...</Text>}
              {!loading &&
                !error &&
                (displayData.orgCount > 0 || displayData.personalCount > 0) && (
                  <Flex gap="xs">
                    {displayData.orgCount > 0 && (
                      <Badge variant="secondary">🏢 {displayData.orgCount} Organization</Badge>
                    )}
                    {displayData.personalCount > 0 && (
                      <Badge variant="secondary">👤 {displayData.personalCount} Personal</Badge>
                    )}
                  </Flex>
                )}
              {!loading && !error && (
                <SheetDescription>
                  {displayData.integrations.length} integration
                  {displayData.integrations.length !== 1 ? "s" : ""} · {displayData.totalTools} tool
                  {displayData.totalTools !== 1 ? "s" : ""}
                </SheetDescription>
              )}
            </Stack>
          </Box>
        </SheetHeader>

        <SheetBody>
          {loading && (
            <Stack spacing="sm">
              <Skeleton height="4xl" width="full" />
              <Skeleton height="4xl" width="full" />
              <Skeleton height="4xl" width="full" />
            </Stack>
          )}

          {error && (
            <Empty icon="⚠️" title="Error loading integrations" description={error.message} />
          )}

          {!loading && !error && displayData.integrations.length === 0 ? (
            <Empty
              icon="🔌"
              title="No integrations"
              description="This agent doesn't have any integrations configured yet."
            />
          ) : !loading && !error ? (
            <div className={styles.integrationsList}>
              {displayData.integrations.map((integration, index) => (
                <Fragment key={integration.id}>
                  {index > 0 && <Separator />}
                  <div>
                    <IntegrationHeader integration={integration} />
                    <ToolsList tools={integration.tools} />
                  </div>
                </Fragment>
              ))}
            </div>
          ) : null}
        </SheetBody>

        <SheetFooter>
          <Button variant="default" onClick={onClose}>
            Close
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
};

export default AgentIntegrationsModal;
