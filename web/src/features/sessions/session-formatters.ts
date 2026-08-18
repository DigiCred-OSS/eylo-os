import type { UserSession } from "@/features/sessions/sessions.types";

function formatSessionEnum(value: string): string {
  return value
    .toLocaleLowerCase()
    .split(/[._-]/u)
    .map((part) => `${part.charAt(0).toLocaleUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function formatSessionContact(contact: UserSession["contact"]): string {
  return (
    contact.name?.trim() ||
    contact.primaryEmail?.trim() ||
    contact.primaryPhone?.trim() ||
    `Unnamed contact · …${contact.id.slice(-8)}`
  );
}

function formatSessionContactDetail(contact: UserSession["contact"]): string {
  const primary = formatSessionContact(contact);
  const details = [contact.primaryEmail, contact.primaryPhone]
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value) && value !== primary);
  return details.length === 0
    ? "No additional contact details"
    : details.join(" · ");
}

function formatSessionDate(value: string | null | undefined): {
  label: string;
  title?: string;
} {
  if (value == null || value === "") {
    return { label: "Not recorded" };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { label: "Invalid date" };
  }
  return {
    label: new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "medium",
    }).format(date),
    title: date.toISOString(),
  };
}

function formatSessionDuration(session: UserSession): string {
  const end = session.endedAt ?? session.disconnectedAt;
  if (end == null) {
    return "Ongoing";
  }
  const milliseconds =
    new Date(end).getTime() - new Date(session.startedAt).getTime();
  if (!Number.isFinite(milliseconds) || milliseconds < 0) {
    return "Not recorded";
  }
  const seconds = Math.round(milliseconds / 1_000);
  const hours = Math.floor(seconds / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  const remainingSeconds = seconds % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return minutes > 0
    ? `${minutes}m ${remainingSeconds}s`
    : `${remainingSeconds}s`;
}

export {
  formatSessionContact,
  formatSessionContactDetail,
  formatSessionDate,
  formatSessionDuration,
  formatSessionEnum,
};
