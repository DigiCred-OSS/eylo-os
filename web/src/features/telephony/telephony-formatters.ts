function formatTelephonyEnum(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toLocaleUpperCase());
}

function formatTelephonyDate(value: string | null | undefined): {
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

function formatCallDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "Not recorded";
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${seconds % 60} sec`;
}

export { formatCallDuration, formatTelephonyDate, formatTelephonyEnum };
