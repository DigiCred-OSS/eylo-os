import type {
  TWidgetDatePickerProps,
  TWidgetFieldValidation,
  TWidgetFormField,
  TWidgetFormProps,
} from "./types";

const NAMED_PATTERNS: Record<string, RegExp> = {
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  phone: /^\+?[0-9()\-\s]{7,20}$/,
  url: /^https?:\/\/.+/i,
};

const isBlank = (value: unknown): boolean => {
  if (value === undefined || value === null) {
    return true;
  }

  if (typeof value === "string") {
    return value.trim().length === 0;
  }

  if (Array.isArray(value)) {
    return value.length === 0;
  }

  return false;
};

const resolveDateFloor = (constraint: string): Date | null => {
  if (constraint === "today") {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today;
  }

  // Use local midnight for date-only strings to avoid UTC/local mismatch
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(constraint);
  if (dateOnly) {
    const [y, m, d] = constraint.split("-").map(Number);
    return new Date(y, m - 1, d, 0, 0, 0, 0);
  }

  const parsed = new Date(constraint);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return parsed;
};

const resolveDateCeiling = (constraint: string): Date | null => {
  const floor = resolveDateFloor(constraint);
  if (!floor) return null;
  // For date-only constraints (including "today"), use end of day
  if (constraint === "today" || /^\d{4}-\d{2}-\d{2}$/.test(constraint)) {
    floor.setHours(23, 59, 59, 999);
  }
  return floor;
};

const MAX_PATTERN_LENGTH = 200;

const validatePattern = (pattern: string, value: string): boolean => {
  const namedPattern = NAMED_PATTERNS[pattern];
  if (namedPattern) {
    return namedPattern.test(value);
  }

  // Guard against ReDoS from LLM-generated patterns
  if (pattern.length > MAX_PATTERN_LENGTH) {
    return true;
  }

  try {
    return new RegExp(pattern).test(value);
  } catch {
    return true;
  }
};

const validationMessage = (
  validation: TWidgetFieldValidation | undefined,
  fallback: string
): string => {
  return validation?.message || fallback;
};

export const validateFieldValue = (field: TWidgetFormField, rawValue: unknown): string | null => {
  if (field.required) {
    if (field.type === "checkbox") {
      if (rawValue !== true) {
        return validationMessage(field.validation, `${field.label} is required.`);
      }
    } else if (isBlank(rawValue)) {
      return validationMessage(field.validation, `${field.label} is required.`);
    }
  }

  if (isBlank(rawValue)) {
    return null;
  }

  const value = typeof rawValue === "string" ? rawValue : String(rawValue);
  const validation = field.validation;

  if (field.type === "select" || field.type === "radio") {
    if (field.options && !field.options.some((option) => option.value === value)) {
      return validationMessage(validation, `${field.label} must use one of the provided options.`);
    }
  }

  if (field.type === "number") {
    const numericValue = typeof rawValue === "number" ? rawValue : Number(rawValue);

    if (Number.isNaN(numericValue)) {
      return validationMessage(validation, `${field.label} must be a valid number.`);
    }

    if (validation?.min !== undefined && numericValue < validation.min) {
      return validationMessage(
        validation,
        `${field.label} must be greater than or equal to ${validation.min}.`
      );
    }

    if (validation?.max !== undefined && numericValue > validation.max) {
      return validationMessage(
        validation,
        `${field.label} must be less than or equal to ${validation.max}.`
      );
    }

    return null;
  }

  if (validation?.minLength !== undefined && value.length < validation.minLength) {
    return validationMessage(
      validation,
      `${field.label} must be at least ${validation.minLength} characters.`
    );
  }

  if (validation?.maxLength !== undefined && value.length > validation.maxLength) {
    return validationMessage(
      validation,
      `${field.label} must be at most ${validation.maxLength} characters.`
    );
  }

  if (validation?.pattern && !validatePattern(validation.pattern, value)) {
    return validationMessage(validation, `${field.label} is not in the expected format.`);
  }

  if (field.type === "email" && !validatePattern("email", value)) {
    return validationMessage(validation, `${field.label} must be a valid email address.`);
  }

  if (field.type === "phone" && !validatePattern("phone", value)) {
    return validationMessage(validation, `${field.label} must be a valid phone number.`);
  }

  if (
    (field.type === "date" || field.type === "datetime") &&
    (validation?.minDate || validation?.maxDate)
  ) {
    const parsedValue = new Date(value);
    if (!Number.isNaN(parsedValue.getTime())) {
      const minDate = validation.minDate ? resolveDateFloor(validation.minDate) : null;
      const maxDate = validation.maxDate ? resolveDateCeiling(validation.maxDate) : null;

      if (minDate && parsedValue < minDate) {
        return validationMessage(
          validation,
          `${field.label} must be on or after ${validation.minDate}.`
        );
      }

      if (maxDate && parsedValue > maxDate) {
        return validationMessage(
          validation,
          `${field.label} must be on or before ${validation.maxDate}.`
        );
      }
    }
  }

  return null;
};

export const validateFormValues = (
  props: TWidgetFormProps,
  values: Record<string, unknown>
): Record<string, string> => {
  return props.fields.reduce<Record<string, string>>((accumulator, field) => {
    const error = validateFieldValue(field, values[field.name]);
    if (error) {
      accumulator[field.name] = error;
    }
    return accumulator;
  }, {});
};

export const validateDatePickerValue = (
  props: TWidgetDatePickerProps,
  value: string
): string | null => {
  const pseudoField: TWidgetFormField = {
    type: props.mode ?? "date",
    name: props.name,
    label: props.label,
    required: props.required,
    validation: props.validation,
  };

  return validateFieldValue(pseudoField, value);
};
