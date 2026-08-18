import type { FC } from "preact/compat";
import type { TWidgetResponseData } from "@eylo";
import { Stack, Text } from "../../design-system";
import styles from "./WidgetResponseSummary.module.css";

type WidgetResponseSummaryProps = {
  response: TWidgetResponseData;
};

/** Humanize a field key: "first_name" → "First name", "agreeTerms" → "Agree terms" */
const formatKey = (key: string): string => {
  const spaced = key
    .replace(/([a-z])([A-Z])/g, "$1 $2") // camelCase
    .replace(/[_-]+/g, " "); // snake_case / kebab-case
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
};

const formatValue = (value: unknown): string => {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

export const WidgetResponseSummary: FC<WidgetResponseSummaryProps> = ({ response }) => {
  const entries = Object.entries(response.data ?? {});
  const hasData = entries.length > 0;

  return (
    <div className={styles.container}>
      <Text as="span" size="xs" variant="muted" semibold className={styles.header}>
        ✓ {response.component === "form" ? "Form" : response.component} submitted
      </Text>
      {hasData && (
        <Stack spacing="xs">
          {entries.map(([key, value]) => (
            <div key={key} className={styles.entry}>
              <Text as="span" size="xs" variant="muted">
                {formatKey(key)}
              </Text>
              <Text as="span" size="xs" semibold>
                {formatValue(value)}
              </Text>
            </div>
          ))}
        </Stack>
      )}
    </div>
  );
};
