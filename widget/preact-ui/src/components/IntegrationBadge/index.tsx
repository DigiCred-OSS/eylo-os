import { type FC } from "preact/compat";
import type { TIntegrationSummary } from "@eylo";
import { Badge } from "../../design-system/components/Badge";
import { Box } from "../../design-system/components/Box";
import { Text } from "../../design-system/components/Typography";
import { cm } from "../../design-system/utils";

interface IntegrationBadgeProps {
  integration?: TIntegrationSummary;
  // Compact mode props (for header use)
  name?: string;
  icon?: string | null;
  hasActiveConnection?: boolean;
  compact?: boolean;
  showStatus?: boolean;
  onClick?: () => void;
}

const IntegrationBadge: FC<IntegrationBadgeProps> = ({
  integration,
  name: compactName,
  icon: compactIcon,
  hasActiveConnection: compactConnection,
  compact = false,
  onClick,
}) => {
  // Use compact props if provided, otherwise fall back to integration object
  const displayName = compactName || integration?.displayName || integration?.name || "Unknown";
  const iconUrl = compactIcon !== undefined ? compactIcon : integration?.iconUrl;
  const isConnected =
    compactConnection !== undefined ? compactConnection : integration?.hasActiveConnection || false;
  const description = integration?.description;
  const connectionKind = integration?.connectionKind;

  // Build title with connection kind info
  const titleText = description || displayName;
  const kindText =
    connectionKind === "ORGANIZATION"
      ? " • Organization-level (requires admin)"
      : connectionKind === "CONTACT"
        ? " • Personal connection"
        : "";
  const fullTitle = titleText + kindText;

  return (
    <Badge variant={"outline"} onClick={onClick} title={fullTitle} style={{ cursor: "pointer" }}>
      {!compact && connectionKind && (
        <>
          <span title={connectionKind === "ORGANIZATION" ? "Organization-level" : "Personal"}>
            {connectionKind === "ORGANIZATION" ? "🏢" : "👤"}
          </span>
          <span
            className={cm(
              "ew-font-bold ew-px-2",
              isConnected ? "ew-text-success" : "ew-text-muted"
            )}
          >
            |
          </span>
        </>
      )}

      {iconUrl && (
        <Box
          display="inline-flex"
          width={compact ? "xs" : "sm"}
          height={compact ? "xs" : "sm"}
          borderRadius="sm"
        >
          <img
            src={iconUrl}
            alt={`${displayName} icon`}
            className="ew-object-contain"
            style={{ width: "100%", height: "100%" }}
          />
        </Box>
      )}

      {!compact && (
        <Text as="span" size="small">
          {displayName}
        </Text>
      )}
    </Badge>
  );
};

export default IntegrationBadge;
