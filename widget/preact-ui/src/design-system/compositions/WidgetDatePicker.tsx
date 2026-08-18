import type { FC } from "preact/compat";
import { useState } from "preact/hooks";
import type { TWidgetInteraction, TWidgetResponseData } from "@eylo";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Text,
} from "../index";
import { validateDatePickerValue } from "./validation";
import type { TWidgetDatePickerPayload } from "./types";
import styles from "./WidgetDatePicker.module.css";

type WidgetDatePickerProps = {
  payload: TWidgetDatePickerPayload;
  onInteraction?: (interaction: TWidgetInteraction) => void;
  isReadOnly?: boolean;
  submission?: TWidgetResponseData | null;
};

const INPUT_TYPE_MAP: Record<string, string> = {
  date: "date",
  time: "time",
  datetime: "datetime-local",
};

const formatDisplayValue = (mode: string, raw: string): string => {
  if (!raw) return "";
  try {
    if (mode === "time") {
      const [h, m] = raw.split(":");
      const hour = Number(h);
      const ampm = hour >= 12 ? "PM" : "AM";
      const h12 = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
      return `${h12}:${m} ${ampm}`;
    }
    if (mode === "date") {
      const d = new Date(raw + "T00:00:00");
      return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
    }
    if (mode === "datetime") {
      const d = new Date(raw);
      return d.toLocaleString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    }
  } catch {
    /* fall through */
  }
  return raw;
};

export const WidgetDatePicker: FC<WidgetDatePickerProps> = ({
  payload,
  onInteraction,
  isReadOnly = false,
  submission = null,
}) => {
  const { props } = payload;
  const mode = props.mode || "date";
  const inputType = INPUT_TYPE_MAP[mode] || "date";

  const submittedValue =
    typeof submission?.data[props.name] === "string" ? (submission.data[props.name] as string) : "";

  const [value, setValue] = useState(submittedValue || props.defaultValue || "");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(Boolean(submission));

  const effectiveReadOnly = isReadOnly || isSubmitted;

  const handleSubmit = (): void => {
    const nextError = validateDatePickerValue(props, value);
    setError(nextError);
    if (nextError) return;

    setIsSubmitted(true);
    onInteraction?.({
      component: "date_picker",
      action: "submit",
      data: { [props.name]: value },
    });
  };

  return (
    <Card border shadow="sm">
      <CardHeader>
        <CardTitle>{props.label}</CardTitle>
        {props.description ? <CardDescription>{props.description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        {effectiveReadOnly && value ? (
          <div className={styles.selectedDisplay}>{formatDisplayValue(mode, value)}</div>
        ) : (
          <Field error={error || undefined}>
            <Input
              type={inputType}
              value={value}
              disabled={effectiveReadOnly}
              onInput={(e) => setValue((e.currentTarget as HTMLInputElement).value)}
            />
          </Field>
        )}
      </CardContent>
      <CardFooter>
        <Button width="full" onClick={handleSubmit} disabled={effectiveReadOnly || !value}>
          {props.submitLabel || "Select"}
        </Button>
        {effectiveReadOnly ? (
          <Text size="xs" variant="muted" align="center">
            Selection confirmed
          </Text>
        ) : null}
      </CardFooter>
    </Card>
  );
};
