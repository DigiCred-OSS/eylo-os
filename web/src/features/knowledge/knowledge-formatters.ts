const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatKnowledgeDate(value: string | null): {
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

function formatKnowledgeVendor(value: string): string {
  const labels: Record<string, string> = {
    pgvector: "pgvector",
    postgres_fts: "Postgres full-text",
  };
  return labels[value] ?? value;
}

function formatKnowledgeScope(value: string): string {
  const labels: Record<string, string> = {
    agent: "Agent",
    conversation: "Conversation",
    organization: "Organization",
  };
  return labels[value] ?? value;
}

function formatChunkingStrategy(value: string): string {
  const labels: Record<string, string> = {
    fixed: "Fixed window",
    markdown: "Markdown headings",
    paragraph: "Paragraph packing",
  };
  return labels[value] ?? value;
}

export {
  formatChunkingStrategy,
  formatKnowledgeDate,
  formatKnowledgeScope,
  formatKnowledgeVendor,
};
