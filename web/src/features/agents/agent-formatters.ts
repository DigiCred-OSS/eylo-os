const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatAgentDate(value: string | undefined): string {
  if (value === undefined) {
    return "Not recorded";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not recorded"
    : dateTimeFormatter.format(date);
}

function formatAgentEnum(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export { formatAgentDate, formatAgentEnum };
