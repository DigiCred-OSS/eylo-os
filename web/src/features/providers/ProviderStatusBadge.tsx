import { Check, CircleOff, Power, ShieldCheck, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface ProviderStatusBadgeProps {
  configured: boolean;
  enabled?: boolean;
  ready: boolean;
  verified: boolean;
}

function ProviderStatusBadge({
  configured,
  enabled,
  ready,
  verified,
}: ProviderStatusBadgeProps) {
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Provider status">
      <StatusItem
        active={configured}
        activeLabel="Configured"
        inactiveLabel="Not configured"
        icon={configured ? Check : X}
      />
      <StatusItem
        active={verified}
        activeLabel="Verified"
        inactiveLabel="Not verified"
        icon={verified ? ShieldCheck : X}
      />
      <StatusItem
        active={ready}
        activeLabel="Ready"
        inactiveLabel="Not ready"
        icon={ready ? Check : CircleOff}
      />
      {enabled === undefined ? null : (
        <StatusItem
          active={enabled}
          activeLabel="Enabled"
          inactiveLabel="Disabled"
          icon={enabled ? Power : CircleOff}
        />
      )}
    </div>
  );
}

function StatusItem({
  active,
  activeLabel,
  icon: Icon,
  inactiveLabel,
}: {
  active: boolean;
  activeLabel: string;
  icon: typeof Check;
  inactiveLabel: string;
}) {
  return (
    <Badge variant={active ? "outline" : "secondary"}>
      <Icon className="size-3" aria-hidden="true" />
      {active ? activeLabel : inactiveLabel}
    </Badge>
  );
}

export { ProviderStatusBadge };
