import type {
  MemoryIntegrity,
  MemoryLevel,
  MemoryReconciliationJob,
  MemoryRelationship,
  MemoryStatus,
} from "@/features/memory/memory.types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatMemoryDate(value: string | null): {
  exact: string | null;
  label: string;
} {
  if (value === null) {
    return { exact: null, label: "Not recorded" };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { exact: null, label: "Not recorded" };
  }
  return { exact: date.toISOString(), label: DATE_FORMATTER.format(date) };
}

function formatMemoryLevel(level: MemoryLevel): string {
  return {
    agent: "Agent",
    conversation: "Conversation",
    user: "User",
  }[level];
}

function formatMemoryStatus(status: MemoryStatus): string {
  return status === "expired" ? "Expired" : "Active";
}

function formatMemoryIntegrity(integrity: MemoryIntegrity): string {
  return {
    checking: "Checking",
    conflicted: "Conflicted",
    consolidated: "Consolidated",
    healthy: "Healthy",
  }[integrity];
}

function formatMemoryRelationship(relationship: MemoryRelationship): string {
  if (relationship.kind === "conflicts_with") {
    return "Conflicts with";
  }
  if (relationship.kind === "duplicate_of") {
    return relationship.memory_role === "source"
      ? "Duplicate of"
      : "Has duplicate";
  }
  return relationship.memory_role === "source" ? "Superseded by" : "Supersedes";
}

function formatReconciliationState(
  state: MemoryReconciliationJob["state"],
): string {
  return state
    .replaceAll("_", " ")
    .replace(/^./, (value) => value.toUpperCase());
}

export {
  formatMemoryDate,
  formatMemoryIntegrity,
  formatMemoryLevel,
  formatMemoryRelationship,
  formatMemoryStatus,
  formatReconciliationState,
};
