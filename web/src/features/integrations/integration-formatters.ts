interface FormattedIntegrationDate {
  label: string;
  title?: string;
}

function formatIntegrationDate(
  value: string | null | undefined,
  fallback = "Unknown",
): FormattedIntegrationDate {
  if (!value) return { label: fallback };
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { label: value };
  return {
    label: new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date),
    title: date.toISOString(),
  };
}

function formatIntegrationIdentifier(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toLocaleUpperCase());
}

export { formatIntegrationDate, formatIntegrationIdentifier };
