import type { ConversationAggregate } from "@/features/conversations/conversations.types";

function formatConversationEnum(value: string): string {
  return value
    .toLocaleLowerCase()
    .split("_")
    .map((part) => `${part.charAt(0).toLocaleUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function formatConversationContact(
  contact: ConversationAggregate["contact"],
): string {
  if (contact == null) {
    return "No contact resolved";
  }
  return (
    contact.name?.trim() ||
    contact.primaryEmail?.trim() ||
    contact.primaryPhone?.trim() ||
    `Unnamed contact · …${contact.id.slice(-8)}`
  );
}

function formatConversationDate(value: string | null | undefined): {
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
      timeStyle: "short",
    }).format(date),
    title: date.toISOString(),
  };
}

function formatDuration(
  startedAt: string | null | undefined,
  endedAt: string | null | undefined,
): string {
  if (startedAt == null || endedAt == null) {
    return "Not complete";
  }
  const duration = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  if (!Number.isFinite(duration) || duration < 0) {
    return "Not recorded";
  }
  const seconds = Math.round(duration / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return minutes === 0
    ? `${remainingSeconds}s`
    : `${minutes}m ${remainingSeconds}s`;
}

function formatTrackDuration(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "Duration unavailable";
  }
  const seconds = Math.max(0, Math.round(value));
  return seconds < 60
    ? `${seconds}s`
    : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function formatMilliseconds(value: number | null | undefined): string {
  return value == null ? "Not complete" : formatTrackDuration(value / 1000);
}

export {
  formatConversationContact,
  formatConversationDate,
  formatConversationEnum,
  formatDuration,
  formatMilliseconds,
  formatTrackDuration,
};
