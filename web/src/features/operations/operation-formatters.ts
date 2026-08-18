function formatOperationEnum(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toLocaleUpperCase());
}
function formatOperationDate(value: string | null): {
  label: string;
  title: string | undefined;
} {
  if (value === null) return { label: "Not recorded", title: undefined };
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
function formatDuration(milliseconds: number | null | undefined): string {
  if (milliseconds === null || milliseconds === undefined)
    return "Not recorded";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  const seconds = Math.round(milliseconds / 1000);
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes} min ${remaining} sec`;
}
export { formatDuration, formatOperationDate, formatOperationEnum };
