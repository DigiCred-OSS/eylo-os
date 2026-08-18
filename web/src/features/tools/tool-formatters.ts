function formatToolEnum(value: string): string {
  return value
    .toLocaleLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toLocaleUpperCase());
}

function formatToolDate(value: string | undefined): {
  label: string;
  title: string | undefined;
} {
  if (value === undefined) {
    return { label: "Not recorded", title: undefined };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { label: "Invalid date", title: value };
  }
  return {
    label: new Intl.DateTimeFormat(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(date),
    title: new Intl.DateTimeFormat(undefined, {
      dateStyle: "full",
      timeStyle: "long",
    }).format(date),
  };
}

export { formatToolDate, formatToolEnum };
