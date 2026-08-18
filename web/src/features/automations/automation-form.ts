import type {
  ScheduleCreateInput,
  ScheduleFormValues,
  ScheduleRecord,
  ScheduleUpdateInput,
} from "@/features/automations/automations.types";

function createDefaultScheduleValues(): ScheduleFormValues {
  const start = new Date(Date.now() + 60 * 60 * 1000);
  start.setSeconds(0, 0);
  return {
    action: "",
    agentId: "",
    endsAt: "",
    key: "",
    misfirePolicy: "coalesce",
    name: "",
    payload: "{}",
    recurrence: "once",
    rule: "",
    startsAt: toZonedLocalDateTime(
      start.toISOString(),
      Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    ),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  };
}

function scheduleToFormValues(schedule: ScheduleRecord): ScheduleFormValues {
  const recurrence = recurrenceForRule(schedule.rule);
  return {
    action: schedule.action,
    agentId: schedule.agent_id,
    endsAt:
      schedule.ends_at === null
        ? ""
        : toZonedLocalDateTime(schedule.ends_at, schedule.timezone),
    key: schedule.key,
    misfirePolicy: schedule.misfire_policy,
    name: schedule.name,
    payload: JSON.stringify(schedule.payload, null, 2),
    recurrence,
    rule: recurrence === "custom" ? (schedule.rule ?? "") : "",
    startsAt: toZonedLocalDateTime(schedule.starts_at, schedule.timezone),
    timezone: schedule.timezone,
  };
}

function validateScheduleValues(values: ScheduleFormValues): string | null {
  if (values.name.trim() === "") return "Name is required.";
  if (values.key.trim() === "") return "Stable key is required.";
  if (!/^[a-z0-9][a-z0-9._-]*$/.test(values.key.trim())) {
    return "Stable key must use lowercase letters, numbers, dots, underscores, or hyphens.";
  }
  if (values.action === "") return "Choose an action.";
  if (values.agentId === "") return "Choose a published Agent.";
  if (values.timezone === "") return "Choose a timezone.";
  if (
    values.startsAt === "" ||
    zonedLocalToIso(values.startsAt, values.timezone) === null
  )
    return "Choose a valid start date and time in this timezone.";
  if (values.recurrence === "custom" && values.rule.trim() === "")
    return "Enter an RRULE for custom recurrence.";
  const start = zonedLocalToIso(values.startsAt, values.timezone);
  const end =
    values.endsAt === ""
      ? null
      : zonedLocalToIso(values.endsAt, values.timezone);
  if (values.endsAt !== "" && end === null)
    return "Choose a valid end date and time in this timezone.";
  if (start !== null && end !== null && Date.parse(end) <= Date.parse(start))
    return "End date must be after the start date.";
  try {
    const payload = JSON.parse(values.payload) as unknown;
    if (
      typeof payload !== "object" ||
      payload === null ||
      Array.isArray(payload)
    )
      return "Payload must be a JSON object.";
  } catch {
    return "Payload must be valid JSON.";
  }
  return null;
}

function toCreateInput(values: ScheduleFormValues): ScheduleCreateInput {
  return {
    action: values.action,
    agent_id: values.agentId,
    ends_at:
      values.endsAt === ""
        ? null
        : zonedLocalToIso(values.endsAt, values.timezone),
    key: values.key.trim(),
    misfire_policy: values.misfirePolicy,
    name: values.name.trim(),
    payload: JSON.parse(values.payload) as Record<string, unknown>,
    rule: ruleForRecurrence(values),
    starts_at:
      zonedLocalToIso(values.startsAt, values.timezone) ?? values.startsAt,
    timezone: values.timezone,
  };
}

function toUpdateInput(
  values: ScheduleFormValues,
  expectedRevision: number,
): ScheduleUpdateInput {
  const input = toCreateInput(values);
  return {
    action: input.action,
    agent_id: input.agent_id,
    ends_at: input.ends_at,
    expected_revision: expectedRevision,
    misfire_policy: input.misfire_policy,
    name: input.name,
    payload: input.payload,
    rule: input.rule,
    starts_at: input.starts_at,
    timezone: input.timezone,
  };
}

function ruleForRecurrence(values: ScheduleFormValues): string | null {
  if (values.recurrence === "once") return null;
  if (values.recurrence === "daily") return "FREQ=DAILY";
  if (values.recurrence === "weekdays")
    return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR";
  if (values.recurrence === "weekly") return "FREQ=WEEKLY";
  return values.rule.trim();
}

function recurrenceForRule(
  rule: string | null,
): ScheduleFormValues["recurrence"] {
  if (rule === null) return "once";
  if (rule === "FREQ=DAILY") return "daily";
  if (rule === "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR") return "weekdays";
  if (rule === "FREQ=WEEKLY") return "weekly";
  return "custom";
}

function toZonedLocalDateTime(value: string, timezone: string): string {
  const date = new Date(value);
  const parts = dateParts(date, timezone);
  if (parts === null) return "";
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function zonedLocalToIso(value: string, timezone: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (match === null) return null;
  const [, year, month, day, hour, minute] = match;
  const wallTime = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
  );
  let candidate = wallTime;
  for (let index = 0; index < 3; index += 1) {
    const parts = dateParts(new Date(candidate), timezone);
    if (parts === null) return null;
    const represented = Date.UTC(
      Number(parts.year),
      Number(parts.month) - 1,
      Number(parts.day),
      Number(parts.hour),
      Number(parts.minute),
    );
    candidate += wallTime - represented;
  }
  const resolved = new Date(candidate);
  return toZonedLocalDateTime(resolved.toISOString(), timezone) === value
    ? resolved.toISOString()
    : null;
}

function dateParts(
  date: Date,
  timezone: string,
): Record<"day" | "hour" | "minute" | "month" | "year", string> | null {
  try {
    const entries = new Intl.DateTimeFormat("en-CA", {
      day: "2-digit",
      hour: "2-digit",
      hourCycle: "h23",
      minute: "2-digit",
      month: "2-digit",
      timeZone: timezone,
      year: "numeric",
    }).formatToParts(date);
    const values = Object.fromEntries(
      entries.map((part) => [part.type, part.value]),
    );
    if (
      ["day", "hour", "minute", "month", "year"].some(
        (key) => typeof values[key] !== "string",
      )
    )
      return null;
    return values as Record<
      "day" | "hour" | "minute" | "month" | "year",
      string
    >;
  } catch {
    return null;
  }
}

export {
  createDefaultScheduleValues,
  scheduleToFormValues,
  toCreateInput,
  toUpdateInput,
  validateScheduleValues,
};
