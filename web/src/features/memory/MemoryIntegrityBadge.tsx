import { Badge } from "@/components/ui/badge";
import { formatMemoryIntegrity } from "@/features/memory/memory-formatters";
import type { MemoryIntegrity } from "@/features/memory/memory.types";

function MemoryIntegrityBadge({ integrity }: { integrity: MemoryIntegrity }) {
  return (
    <Badge variant={integrity === "consolidated" ? "secondary" : "outline"}>
      {formatMemoryIntegrity(integrity)}
    </Badge>
  );
}

export { MemoryIntegrityBadge };
