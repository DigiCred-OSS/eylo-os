import { formatDistance } from "date-fns";

/**
 * Date and time formatting utilities
 */

/**
 * Formats a timestamp with smart relative date display
 *
 * - Today: Just time (e.g., "2:30 PM")
 * - Yesterday: "Yesterday 2:30 PM"
 * - Last 7 days: Day of week + time (e.g., "Mon 2:30 PM")
 * - This year: Month and day + time (e.g., "Jan 15, 2:30 PM")
 * - Older: Full date + time (e.g., "Jan 15, 2024, 2:30 PM")
 *
 * @param date - The date to format (Date object or ISO string)
 * @returns Formatted timestamp string
 */
export const formatMessageTimestamp = (date: Date | string): string => {
  const now = new Date();
  const messageDate = new Date(date);
  const diffInHours = (now.getTime() - messageDate.getTime()) / (1000 * 60 * 60);
  const diffInDays = Math.floor(diffInHours / 24);

  // Less than 24 hours - show time only
  if (diffInHours < 24 && now.getDate() === messageDate.getDate()) {
    return messageDate.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Yesterday
  if (diffInDays === 1 || (diffInHours < 48 && now.getDate() - messageDate.getDate() === 1)) {
    return `Yesterday ${messageDate.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }

  // Less than 7 days - show day of week
  if (diffInDays < 7) {
    return messageDate.toLocaleDateString([], {
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Less than a year - show month and day
  if (now.getFullYear() === messageDate.getFullYear()) {
    return messageDate.toLocaleDateString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Older than a year - show full date
  return messageDate.toLocaleDateString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

/**
 * Formats a date as a relative time string using date-fns
 *
 * @param date - The date to format (Date object or ISO string)
 * @returns Relative time string (e.g., "2 hours ago", "3 days ago")
 *
 * @example
 * formatRelativeTime(new Date()) // "less than a minute ago"
 * formatRelativeTime(new Date(Date.now() - 1000 * 60 * 60 * 2)) // "about 2 hours ago"
 */
export const formatRelativeTime = (date: Date | string): string => {
  if (!date) return "";
  const targetDate = new Date(date);
  const now = new Date();
  return `${formatDistance(targetDate, now)} ago`;
};

/**
 * Formats a conversation timestamp with relative time
 * Used primarily for conversation list timestamps
 *
 * @param date - The date to format (Date object or ISO string)
 * @returns Relative time string (e.g., "2 hours ago") or empty string if no date
 *
 * @example
 * formatTimestamp(conversation.updatedAt) // "3 days ago"
 */
export const formatTimestamp = (date?: Date | string): string => {
  if (!date) return "";
  const targetDate = new Date(date);
  const now = new Date();
  return `${formatDistance(targetDate, now)} ago`;
};
