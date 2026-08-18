function formatCampaignEnum(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toLocaleUpperCase());
}

function formatCampaignDate(value: string | null | undefined): {
  label: string;
  title?: string;
} {
  if (value === null || value === undefined) return { label: "Not recorded" };
  const date = new Date(value);
  if (Number.isNaN(date.getTime()))
    return { label: "Invalid date", title: value };
  return {
    label: new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date),
    title: new Intl.DateTimeFormat(undefined, {
      dateStyle: "full",
      timeStyle: "long",
    }).format(date),
  };
}

function campaignProgress(
  completed: number,
  failed: number,
  total: number,
): { label: string; percent: number } {
  if (total <= 0) return { label: "No recipients", percent: 0 };
  const terminal = Math.min(total, Math.max(0, completed + failed));
  return {
    label: `${terminal.toLocaleString()} / ${total.toLocaleString()}`,
    percent: Math.round((terminal / total) * 100),
  };
}

export { campaignProgress, formatCampaignDate, formatCampaignEnum };
