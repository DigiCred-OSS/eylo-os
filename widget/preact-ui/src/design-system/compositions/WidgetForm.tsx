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
  Checkbox,
  Field,
  Input,
  RadioGroup,
  RadioGroupItem,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Stack,
  Textarea,
} from "../index";
import { validateFieldValue, validateFormValues } from "./validation";
import type { TWidgetFormField, TWidgetFormPayload } from "./types";

type WidgetFormProps = {
  payload: TWidgetFormPayload;
  onInteraction?: (interaction: TWidgetInteraction) => void;
  isReadOnly?: boolean;
  submission?: TWidgetResponseData | null;
};

const getInputType = (field: TWidgetFormField): string => {
  if (field.type === "phone") return "tel";
  if (field.type === "datetime") return "datetime-local";
  return field.type;
};

const buildInitialValues = (fields: TWidgetFormField[]): Record<string, unknown> => {
  return fields.reduce<Record<string, unknown>>((accumulator, field) => {
    if (field.defaultValue !== undefined) {
      accumulator[field.name] = field.defaultValue;
      return accumulator;
    }

    accumulator[field.name] = field.type === "checkbox" ? false : "";
    return accumulator;
  }, {});
};

export const WidgetForm: FC<WidgetFormProps> = ({
  payload,
  onInteraction,
  isReadOnly = false,
  submission = null,
}) => {
  const { props } = payload;
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const initialValues = buildInitialValues(props.fields);
    return submission?.data ? { ...initialValues, ...submission.data } : initialValues;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitted, setIsSubmitted] = useState(Boolean(submission));

  const effectiveReadOnly = isReadOnly || isSubmitted;

  const updateValue = (field: TWidgetFormField, nextValue: unknown): void => {
    setValues((previous) => ({
      ...previous,
      [field.name]: nextValue,
    }));

    setErrors((previous) => {
      const nextErrors = { ...previous };
      const nextError = validateFieldValue(field, nextValue);

      if (nextError) {
        nextErrors[field.name] = nextError;
      } else {
        delete nextErrors[field.name];
      }

      return nextErrors;
    });
  };

  const handleSubmit = (): void => {
    const nextErrors = validateFormValues(props, values);
    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setIsSubmitted(true);
    onInteraction?.({
      component: "form",
      action: "submit",
      data: values,
    });
  };

  const handleCancel = (): void => {
    onInteraction?.({
      component: "form",
      action: "cancel",
      data: values,
    });
  };

  const renderField = (field: TWidgetFormField) => {
    const fieldValue = values[field.name];
    const fieldError = errors[field.name];

    if (field.type === "textarea") {
      return (
        <Field
          key={field.name}
          label={field.label}
          htmlFor={field.name}
          required={field.required}
          error={fieldError}
        >
          <Textarea
            id={field.name}
            value={String(fieldValue ?? "")}
            placeholder={field.placeholder}
            disabled={effectiveReadOnly}
            onInput={(event) =>
              updateValue(field, (event.currentTarget as HTMLTextAreaElement).value)
            }
          />
        </Field>
      );
    }

    if (field.type === "select") {
      return (
        <Field key={field.name} label={field.label} required={field.required} error={fieldError}>
          <Select
            value={typeof fieldValue === "string" ? fieldValue : undefined}
            onValueChange={(nextValue) => updateValue(field, nextValue)}
            disabled={effectiveReadOnly}
          >
            <SelectTrigger
              error={Boolean(fieldError)}
              placeholder={field.placeholder || "Select..."}
            >
              <SelectValue placeholder={field.placeholder || "Select..."} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      );
    }

    if (field.type === "radio") {
      return (
        <Field key={field.name} label={field.label} required={field.required} error={fieldError}>
          <RadioGroup
            value={typeof fieldValue === "string" ? fieldValue : undefined}
            onValueChange={(nextValue) => updateValue(field, nextValue)}
            disabled={effectiveReadOnly}
          >
            {field.options?.map((option) => (
              <RadioGroupItem
                key={option.value}
                value={option.value}
                label={option.label}
                description={option.description}
              />
            ))}
          </RadioGroup>
        </Field>
      );
    }

    if (field.type === "checkbox") {
      return (
        <Field key={field.name} label={field.label} required={field.required} error={fieldError}>
          <Checkbox
            checked={Boolean(fieldValue)}
            disabled={effectiveReadOnly}
            onChange={(checked) => updateValue(field, checked)}
            label={field.placeholder || "Enable"}
          />
        </Field>
      );
    }

    return (
      <Field
        key={field.name}
        label={field.label}
        htmlFor={field.name}
        required={field.required}
        error={fieldError}
      >
        <Input
          id={field.name}
          type={getInputType(field)}
          value={fieldValue === undefined ? "" : String(fieldValue)}
          min={field.validation?.min}
          max={field.validation?.max}
          placeholder={field.placeholder}
          error={Boolean(fieldError)}
          disabled={effectiveReadOnly}
          onInput={(event) => {
            const nextValue = (event.currentTarget as HTMLInputElement).value;
            updateValue(
              field,
              field.type === "number" && nextValue ? Number(nextValue) : nextValue
            );
          }}
        />
      </Field>
    );
  };

  return (
    <Card border shadow="sm">
      <form
        onSubmit={(e: Event) => {
          e.preventDefault();
          handleSubmit();
        }}
      >
        <CardHeader>
          <CardTitle>{props.title}</CardTitle>
          {props.description ? <CardDescription>{props.description}</CardDescription> : null}
        </CardHeader>
        <CardContent>
          <Stack spacing="md">{props.fields.map(renderField)}</Stack>
        </CardContent>
        <CardFooter>
          <Stack spacing="sm">
            <Button type="submit" width="full" disabled={effectiveReadOnly}>
              {props.submitLabel || "Submit"}
            </Button>
            {!effectiveReadOnly && props.cancelLabel ? (
              <Button width="full" variant="outline" onClick={handleCancel}>
                {props.cancelLabel}
              </Button>
            ) : null}
          </Stack>
        </CardFooter>
      </form>
    </Card>
  );
};
