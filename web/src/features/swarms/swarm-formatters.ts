const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatSwarmDate(value: string | null | undefined): {
  exact: string | null;
  label: string;
} {
  if (value === null || value === undefined) {
    return { exact: null, label: "Not recorded" };
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? { exact: null, label: "Not recorded" }
    : { exact: date.toISOString(), label: dateTimeFormatter.format(date) };
}

function formatSwarmEnum(value: string): string {
  return value
    .toLocaleLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toLocaleUpperCase() + part.slice(1))
    .join(" ");
}

export { formatSwarmDate, formatSwarmEnum };
