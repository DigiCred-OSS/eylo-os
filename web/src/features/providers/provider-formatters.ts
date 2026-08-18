import type { ProviderFieldValue } from "@/features/providers/providers.types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatProviderIdentifier(value: string): string {
  const knownLabels: Record<string, string> = {
    api: "API",
    aws: "AWS",
    cpu: "CPU",
    id: "ID",
    ip: "IP",
    llm: "LLM",
    mb: "MB",
    smtp: "SMTP",
    stt: "STT",
    tls: "TLS",
    tts: "TTS",
    url: "URL",
    vad: "VAD",
    webrtc: "WebRTC",
  };
  return value
    .replaceAll("-", "_")
    .split("_")
    .filter(Boolean)
    .map((part) => knownLabels[part.toLowerCase()] ?? capitalize(part))
    .join(" ");
}

function formatProviderDate(value: string | null): {
  exact: string | null;
  label: string;
} {
  if (value === null) {
    return { exact: null, label: "Not verified" };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { exact: null, label: "Not recorded" };
  }
  return { exact: date.toISOString(), label: DATE_FORMATTER.format(date) };
}

function formatProviderFieldValue(value: ProviderFieldValue): string {
  if (value === null || value === "") {
    return "Not configured";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat().format(value);
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? "Not configured" : value.join(", ");
  }
  return value;
}

function capitalize(value: string): string {
  return value.length === 0
    ? value
    : `${value[0]?.toUpperCase() ?? ""}${value.slice(1).toLowerCase()}`;
}

export {
  formatProviderDate,
  formatProviderFieldValue,
  formatProviderIdentifier,
};
