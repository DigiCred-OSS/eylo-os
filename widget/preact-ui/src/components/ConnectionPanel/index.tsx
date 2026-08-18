// components/ConnectionPanel/index.tsx
import type { FC } from "preact/compat";
import { useEffect, useState } from "preact/hooks";

import type {
  AuthRequirement,
  ConnectionStateManager,
  CuratedCredentialInput,
} from "@eylo/modules/conversation";
import { useLogger } from "../../hooks/useEyloAdvanced";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetBody,
} from "../../design-system/components/Sheet";
import { Button } from "../../design-system/components/Button";
import { Badge } from "../../design-system/components/Badge";
import { Text } from "../../design-system/components/Typography";
import { Stack } from "../../design-system/components/Stack";
import { Box } from "../../design-system/components/Box";
import { Flex } from "../../design-system/components/Flex";
import { Field } from "../../design-system/components/Field";
import { Input } from "../../design-system/components/Input";

interface ConnectionPanelProps {
  connectionManager: ConnectionStateManager;
}

// Subcomponent for individual auth requirement card
const AuthRequirementCard: FC<{
  auth: AuthRequirement;
  onConnect: (auth: AuthRequirement, credentials?: CuratedCredentialInput) => void;
  onRetry: (auth: AuthRequirement, credentials?: CuratedCredentialInput) => void;
  onDismiss: (requirementId: string) => void;
}> = ({ auth, onConnect, onRetry, onDismiss }) => {
  const [apiKey, setApiKey] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const isConnecting = auth.status === "connecting";
  const isFailed = auth.status === "failed";
  const usesApiKey = auth.auth_kind === "api_key";
  const usesBasic = auth.auth_kind === "basic";
  const credentials = usesApiKey ? { apiKey } : usesBasic ? { username, password } : undefined;
  const isCredentialReady = usesApiKey
    ? Boolean(apiKey)
    : usesBasic
      ? Boolean(username && password)
      : true;

  const handleAction = () => {
    if (isFailed) {
      onRetry(auth, credentials);
    } else {
      onConnect(auth, credentials);
    }
  };

  return (
    <Box padding="sm" borderRadius="sm" background="muted-subtle" border>
      <Stack spacing="xs">
        <Flex align="center" gap="xs">
          <Text size="small" semibold>
            {auth.integration_name}
          </Text>
          {isConnecting && <Badge variant="secondary">Connecting...</Badge>}
          {isFailed && <Badge variant="destructive">Failed</Badge>}
        </Flex>

        <Text size="xs" className={isFailed ? "ew-text-destructive" : "ew-text-muted"}>
          {isFailed && auth.error ? `Connection failed: ${auth.error}` : auth.message}
        </Text>

        {usesApiKey && (
          <Field label="API key" htmlFor={`${auth.id}-api-key`} required>
            <Input
              id={`${auth.id}-api-key`}
              type="password"
              value={apiKey}
              onInput={(event) => setApiKey(event.currentTarget.value)}
              autocomplete="off"
              disabled={isConnecting}
            />
          </Field>
        )}

        {usesBasic && (
          <Stack spacing="xs">
            <Field label="Username" htmlFor={`${auth.id}-username`} required>
              <Input
                id={`${auth.id}-username`}
                value={username}
                onInput={(event) => setUsername(event.currentTarget.value)}
                autocomplete="username"
                disabled={isConnecting}
              />
            </Field>
            <Field label="Password or token" htmlFor={`${auth.id}-password`} required>
              <Input
                id={`${auth.id}-password`}
                type="password"
                value={password}
                onInput={(event) => setPassword(event.currentTarget.value)}
                autocomplete="current-password"
                disabled={isConnecting}
              />
            </Field>
          </Stack>
        )}

        <Flex gap="sm">
          <Button
            variant="default"
            size="sm"
            onClick={handleAction}
            disabled={isConnecting || !isCredentialReady}
          >
            {isConnecting ? "Connecting..." : isFailed ? "Retry" : "Connect"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDismiss(auth.id)}
            disabled={isConnecting}
          >
            Dismiss
          </Button>
        </Flex>
      </Stack>
    </Box>
  );
};

const ConnectionPanel: FC<ConnectionPanelProps> = ({ connectionManager }) => {
  const { debug, error: logError } = useLogger();
  const [pendingAuths, setPendingAuths] = useState<AuthRequirement[]>([]);
  const [isExpanded, setIsExpanded] = useState(true);

  useEffect(() => {
    // Subscribe to connection state changes
    const unsubscribe = connectionManager.subscribe((authReq) => {
      debug("Auth requirement updated:", authReq);
      setPendingAuths(connectionManager.getPendingAuths());
    });

    // Initial load
    setPendingAuths(connectionManager.getPendingAuths());

    return unsubscribe;
  }, [connectionManager, debug]);

  const handleConnect = async (auth: AuthRequirement, credentials?: CuratedCredentialInput) => {
    try {
      debug(`Connecting ${auth.id}`);
      if (auth.auth_kind !== "oauth2") {
        await connectionManager.connectWithCredentials(auth.id, credentials || {});
      } else {
        await connectionManager.openOAuthPopup(auth.id);
      }
      debug(`Successfully connected ${auth.id}`);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Connection failed";
      logError(`Failed to connect ${auth.id}:`, errorMsg);
    }
  };

  const handleRetry = async (auth: AuthRequirement, credentials?: CuratedCredentialInput) => {
    connectionManager.retryAuth(auth.id);
    await handleConnect(auth, credentials);
  };

  const handleDismiss = (integrationId: string) => {
    connectionManager.dismissAuth(integrationId);
  };

  const displayAuths = pendingAuths;

  const isOpen = displayAuths.length > 0;
  const authCount = displayAuths.length;

  return (
    <Sheet open={isOpen}>
      <SheetContent
        showHandle={true}
        dismissible={false}
        onToggle={() => setIsExpanded(!isExpanded)}
        shadow="md"
      >
        {!isExpanded ? (
          // Collapsed view - just show count and expand button
          <Box padding="sm">
            <Flex align="center" justify="between" gap="sm">
              <Flex align="center" gap="xs">
                <Badge variant="destructive">!</Badge>
                <Text size="small" semibold>
                  {authCount} integration{authCount !== 1 ? "s" : ""} need
                  {authCount === 1 ? "s" : ""} connection
                </Text>
              </Flex>
              <Button variant="ghost" size="sm" onClick={() => setIsExpanded(true)}>
                Show
              </Button>
            </Flex>
          </Box>
        ) : (
          // Expanded view - show all with scroll
          <>
            <SheetHeader>
              <SheetTitle>Required Connections ({authCount})</SheetTitle>
            </SheetHeader>
            <SheetBody>
              <Stack spacing="sm">
                {displayAuths.map((auth) => (
                  <AuthRequirementCard
                    key={auth.id}
                    auth={auth}
                    onConnect={handleConnect}
                    onRetry={handleRetry}
                    onDismiss={handleDismiss}
                  />
                ))}
              </Stack>
            </SheetBody>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default ConnectionPanel;
