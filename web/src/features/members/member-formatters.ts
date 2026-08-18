import type { MemberStatus } from "@/features/members/members.types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatMemberDate(value: string | null | undefined): {
  exact: string | null;
  label: string;
} {
  if (value === null || value === undefined)
    return { exact: null, label: "Never" };
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? { exact: null, label: "Unavailable" }
    : { exact: date.toISOString(), label: DATE_FORMATTER.format(date) };
}

function formatMemberStatus(status: MemberStatus): string {
  return status.charAt(0) + status.slice(1).toLowerCase();
}

export { formatMemberDate, formatMemberStatus };
