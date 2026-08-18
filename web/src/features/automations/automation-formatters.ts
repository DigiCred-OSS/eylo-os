function formatAutomationEnum(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toLocaleUpperCase());
}

function formatAutomationDate(value: string | null): {
  label: string;
  title: string | undefined;
} {
  if (value === null) return { label: "Not scheduled", title: undefined };
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

function formatRecurrence(rule: string | null): string {
  if (rule === null) return "One time";
  if (rule === "FREQ=DAILY") return "Daily";
  if (rule === "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR") return "Weekdays";
  if (rule === "FREQ=WEEKLY") return "Weekly";
  return rule;
}

export { formatAutomationDate, formatAutomationEnum, formatRecurrence };
