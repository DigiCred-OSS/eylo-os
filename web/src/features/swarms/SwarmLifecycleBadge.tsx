import { Badge } from "@/components/ui/badge";
import { formatSwarmEnum } from "@/features/swarms/swarm-formatters";

function SwarmLifecycleBadge({ lifecycle }: { lifecycle: string }) {
  return <Badge variant="outline">{formatSwarmEnum(lifecycle)}</Badge>;
}

export { SwarmLifecycleBadge };
