import { Badge } from "@/components/ui/badge";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import type { AgentStatus } from "@/features/agents/agents.types";

function AgentStatusBadge({ status }: { status: AgentStatus }) {
  return <Badge variant="outline">{formatAgentEnum(status)}</Badge>;
}

export { AgentStatusBadge };
