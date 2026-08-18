function formatVoiceDate(value: string): {
  exact: string | null;
  label: string;
} {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { exact: null, label: "Unknown" };
  }
  const differenceSeconds = Math.round((date.getTime() - Date.now()) / 1_000);
  const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const intervals = [
    [60, "minute"],
    [60, "hour"],
    [24, "day"],
    [30, "month"],
    [12, "year"],
  ] as const;
  let amount = differenceSeconds;
  let unit: Intl.RelativeTimeFormatUnit = "second";
  for (const [size, nextUnit] of intervals) {
    if (Math.abs(amount) < size) {
      break;
    }
    amount = Math.round(amount / size);
    unit = nextUnit;
  }
  return { exact: date.toISOString(), label: relative.format(amount, unit) };
}

export { formatVoiceDate };
