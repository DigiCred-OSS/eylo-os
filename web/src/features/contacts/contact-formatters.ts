import type { ContactLifecycle } from "@/features/contacts/contacts.types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatContactDate(value: string | null | undefined): {
  exact: string | null;
  label: string;
} {
  if (value === null || value === undefined)
    return { exact: null, label: "Not recorded" };
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? { exact: null, label: "Unavailable" }
    : { exact: date.toISOString(), label: DATE_FORMATTER.format(date) };
}

function formatContactLifecycle(lifecycle: ContactLifecycle): string {
  return lifecycle === "deletion_pending" ? "Deletion pending" : "Active";
}

export { formatContactDate, formatContactLifecycle };
