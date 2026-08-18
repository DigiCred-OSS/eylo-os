import type { FC } from "preact/compat";

import BackIcon from "../../assets/icons/BackIcon";
import { EyloIcon } from "../../assets/icons/Eylo";
import { useConnectionStatus } from "../../hooks/useEyloStore";
import { Button } from "../../design-system/components/Button";
import { Badge } from "../../design-system/components/Badge";
import { Flex } from "../../design-system/components/Flex";
import { Text } from "../../design-system/components/Typography";
import type { TChatHeader } from "./types";
import styles from "./ChatHeader.module.css";

const OnlineBadge: FC<{ isConnected: boolean }> = ({ isConnected }) => (
  <div className={styles.connectionIndicator} aria-label={isConnected ? "Connected" : "Offline"}>
    <EyloIcon status={isConnected ? "online" : "offline"} />
  </div>
);

const cleanStatusMessage = (message: string): string =>
  message.replace(/^(?:💡|🤖|🔧|🚀|💭|⚙️|✨|💬)\s*/u, "");

const ChatHeader: FC<TChatHeader> = ({ title, onBack, agentStatus }) => {
  const { isConnected } = useConnectionStatus();

  const defaultTitle = isConnected ? "Hey! How can we help?" : "We'll respond when back online";

  const isError = agentStatus?.type === "error";
  const statusText = agentStatus ? cleanStatusMessage(agentStatus.message) : "";
  const isAgentWorking = agentStatus && !isError;

  return (
    <div id="ew-chat-header">
      <div className="container">
        {onBack ? (
          <Button
            variant="outline"
            size="icon"
            onClick={onBack}
            aria-label="Go back"
            className={isAgentWorking ? styles.backButtonBusy : ""}
          >
            <BackIcon />
          </Button>
        ) : (
          <OnlineBadge isConnected={isConnected} />
        )}
        {agentStatus ? (
          <Flex align="center" gap="xs" className={styles.statusContent}>
            {agentStatus.icon || (!isError && <span className={styles.statusIndicator} />)}
            {isError ? (
              <Badge variant="destructive" className={styles.errorBadge} role="alert">
                <Text as="span" size="small">
                  {statusText}
                </Text>
              </Badge>
            ) : (
              <Text as="span" size="small" className={styles.statusText} role="status">
                {statusText}
              </Text>
            )}
          </Flex>
        ) : (
          <Text as="span" semibold className={styles.title} title={title || defaultTitle}>
            {title || defaultTitle}
          </Text>
        )}
      </div>
    </div>
  );
};

export default ChatHeader;
