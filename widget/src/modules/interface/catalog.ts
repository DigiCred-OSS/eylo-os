import type { TRegisteredWidgetComponent, TWidgetPayloadEnvelope, TWidgetValidationIssue } from "./types";
import { registerWidgetComponents } from "./service";

type TWidgetButtonVariant = "primary" | "secondary" | "destructive" | "ghost" | "outline" | "link";

type TWidgetFormFieldType =
  | "text"
  | "email"
  | "phone"
  | "number"
  | "textarea"
  | "select"
  | "radio"
  | "checkbox"
  | "date"
  | "time"
  | "datetime";

type TWidgetFieldValidation = {
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  pattern?: string;
  message?: string;
  minDate?: string;
  maxDate?: string;
};

type TWidgetOption = {
  value: string;
  label: string;
  description?: string;
};

type TWidgetFormField = {
  type: TWidgetFormFieldType;
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  defaultValue?: unknown;
  options?: TWidgetOption[];
  validation?: TWidgetFieldValidation;
};

type TWidgetFormProps = {
  title: string;
  description?: string;
  fields: TWidgetFormField[];
  submitLabel?: string;
  cancelLabel?: string;
};

type TWidgetButtonGroupButton = {
  value: string;
  label: string;
  variant?: TWidgetButtonVariant;
  icon?: string;
};

type TWidgetButtonGroupProps = {
  question?: string;
  buttons: TWidgetButtonGroupButton[];
  layout?: "horizontal" | "vertical";
};

type TWidgetCardListCard = {
  id: string;
  title: string;
  description?: string;
  image?: string;
  price?: string;
  badge?: string;
  features?: string[];
};

type TWidgetCardListProps = {
  title?: string;
  description?: string;
  selectionMode?: "single" | "multiple";
  cards: TWidgetCardListCard[];
  submitLabel?: string;
};

type TWidgetDatePickerProps = {
  label: string;
  name: string;
  description?: string;
  mode?: "date" | "time" | "datetime";
  placeholder?: string;
  required?: boolean;
  defaultValue?: string;
  validation?: Pick<TWidgetFieldValidation, "minDate" | "maxDate" | "message">;
  submitLabel?: string;
};

type TWidgetFormPayload = TWidgetPayloadEnvelope<"form", TWidgetFormProps>;
type TWidgetButtonGroupPayload = TWidgetPayloadEnvelope<"button_group", TWidgetButtonGroupProps>;
type TWidgetCardListPayload = TWidgetPayloadEnvelope<"card_list", TWidgetCardListProps>;
type TWidgetDatePickerPayload = TWidgetPayloadEnvelope<"date_picker", TWidgetDatePickerProps>;

// Layout component types (structural only — no submissions)
type TWidgetStackProps = {
  spacing?: "xs" | "sm" | "md" | "lg" | "xl";
};

type TWidgetRowProps = {
  spacing?: "xs" | "sm" | "md" | "lg" | "xl";
  align?: "start" | "center" | "end" | "stretch";
};

type TWidgetSectionProps = {
  title?: string;
  description?: string;
  collapsible?: boolean;
};

export type TWidgetStackPayload = TWidgetPayloadEnvelope<"stack", TWidgetStackProps>;
export type TWidgetRowPayload = TWidgetPayloadEnvelope<"row", TWidgetRowProps>;
export type TWidgetSectionPayload = TWidgetPayloadEnvelope<"section", TWidgetSectionProps>;

const stringSchema = (optional = false) => ({ type: "string" as const, optional });
const numberSchema = (optional = false) => ({ type: "number" as const, optional });
const booleanSchema = (optional = false) => ({ type: "boolean" as const, optional });
const anySchema = (optional = false) => ({ type: "any" as const, optional });

const optionSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["value", "label"],
  properties: {
    value: stringSchema(),
    label: stringSchema(),
    description: stringSchema(true),
  },
};

const fieldValidationSchema = {
  type: "object" as const,
  additionalProperties: false,
  properties: {
    minLength: numberSchema(true),
    maxLength: numberSchema(true),
    min: numberSchema(true),
    max: numberSchema(true),
    pattern: stringSchema(true),
    message: stringSchema(true),
    minDate: stringSchema(true),
    maxDate: stringSchema(true),
  },
};

const formPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: {
      type: "string" as const,
      enum: ["form"],
    },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["title", "fields"],
      properties: {
        title: stringSchema(),
        description: stringSchema(true),
        fields: {
          type: "array" as const,
          minItems: 1,
          items: {
            type: "object" as const,
            additionalProperties: false,
            required: ["type", "name", "label"],
            properties: {
              type: {
                type: "string" as const,
                enum: [
                  "text",
                  "email",
                  "phone",
                  "number",
                  "textarea",
                  "select",
                  "radio",
                  "checkbox",
                  "date",
                  "time",
                  "datetime",
                ],
              },
              name: stringSchema(),
              label: stringSchema(),
              placeholder: stringSchema(true),
              required: booleanSchema(true),
              defaultValue: anySchema(true),
              options: {
                type: "array" as const,
                optional: true,
                items: optionSchema,
                minItems: 1,
              },
              validation: {
                ...fieldValidationSchema,
                optional: true,
              },
            },
          },
        },
        submitLabel: stringSchema(true),
        cancelLabel: stringSchema(true),
      },
    },
  },
};

const buttonGroupPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: {
      type: "string" as const,
      enum: ["button_group"],
    },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["buttons"],
      properties: {
        question: stringSchema(true),
        layout: {
          type: "string" as const,
          enum: ["horizontal", "vertical"],
          optional: true,
        },
        buttons: {
          type: "array" as const,
          minItems: 1,
          items: {
            type: "object" as const,
            additionalProperties: false,
            required: ["value", "label"],
            properties: {
              value: stringSchema(),
              label: stringSchema(),
              variant: {
                type: "string" as const,
                enum: ["primary", "secondary", "destructive", "ghost", "outline", "link"],
                optional: true,
              },
              icon: stringSchema(true),
            },
          },
        },
      },
    },
  },
};

const cardListPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: {
      type: "string" as const,
      enum: ["card_list"],
    },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["cards"],
      properties: {
        title: stringSchema(true),
        description: stringSchema(true),
        selectionMode: {
          type: "string" as const,
          enum: ["single", "multiple"],
          optional: true,
        },
        submitLabel: stringSchema(true),
        cards: {
          type: "array" as const,
          minItems: 1,
          items: {
            type: "object" as const,
            additionalProperties: false,
            required: ["id", "title"],
            properties: {
              id: stringSchema(),
              title: stringSchema(),
              description: stringSchema(true),
              image: stringSchema(true),
              price: stringSchema(true),
              badge: stringSchema(true),
              features: {
                type: "array" as const,
                optional: true,
                items: stringSchema(),
              },
            },
          },
        },
      },
    },
  },
};

const datePickerPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: {
      type: "string" as const,
      enum: ["date_picker"],
    },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["label", "name"],
      properties: {
        label: stringSchema(),
        name: stringSchema(),
        description: stringSchema(true),
        mode: {
          type: "string" as const,
          enum: ["date", "time", "datetime"],
          optional: true,
        },
        placeholder: stringSchema(true),
        required: booleanSchema(true),
        defaultValue: stringSchema(true),
        submitLabel: stringSchema(true),
        validation: {
          type: "object" as const,
          additionalProperties: false,
          optional: true,
          properties: {
            minDate: stringSchema(true),
            maxDate: stringSchema(true),
            message: stringSchema(true),
          },
        },
      },
    },
  },
};

const alertPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: {
      type: "string" as const,
      enum: ["alert"],
    },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["message"],
      properties: {
        title: stringSchema(true),
        message: stringSchema(),
        dismissible: booleanSchema(true),
        severity: {
          type: "string" as const,
          enum: ["info", "success", "warning", "error"],
          optional: true,
        },
      },
    },
  },
};

// ----------- New Tier-1 content component schemas -----------

const textPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["text"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["content"],
      properties: {
        content: stringSchema(),
        variant: {
          type: "string" as const,
          enum: ["body", "heading", "caption", "code"],
          optional: true,
        },
      },
    },
  },
};

const imagePayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["image"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["src", "alt"],
      properties: {
        src: stringSchema(),
        alt: stringSchema(),
        caption: stringSchema(true),
        width: numberSchema(true),
        height: numberSchema(true),
      },
    },
  },
};

type TWidgetProgressStep = {
  label: string;
  status: "pending" | "active" | "completed";
};

const progressPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["progress"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["currentStep", "totalSteps"],
      properties: {
        currentStep: numberSchema(),
        totalSteps: numberSchema(),
        label: stringSchema(true),
        steps: {
          type: "array" as const,
          optional: true,
          items: {
            type: "object" as const,
            additionalProperties: false,
            required: ["label", "status"],
            properties: {
              label: stringSchema(),
              status: {
                type: "string" as const,
                enum: ["pending", "active", "completed"],
              },
            },
          },
        },
      },
    },
  },
};

const tablePayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["table"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      required: ["columns", "rows"],
      properties: {
        columns: {
          type: "array" as const,
          minItems: 1,
          items: {
            type: "object" as const,
            additionalProperties: false,
            required: ["key", "label"],
            properties: {
              key: stringSchema(),
              label: stringSchema(),
              align: {
                type: "string" as const,
                enum: ["left", "center", "right"],
                optional: true,
              },
            },
          },
        },
        rows: {
          type: "array" as const,
          minItems: 1,
          items: anySchema(),
        },
        caption: stringSchema(true),
      },
    },
  },
};

const dividerPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["divider"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      properties: {
        label: stringSchema(true),
      },
    },
  },
};

const validateProgressPayload = (payload: { props: { currentStep: number; totalSteps: number; steps?: TWidgetProgressStep[] } }): TWidgetValidationIssue[] => {
  const issues: TWidgetValidationIssue[] = [];
  if (payload.props.currentStep > payload.props.totalSteps) {
    issues.push({ path: "$.props.currentStep", message: "currentStep cannot exceed totalSteps." });
  }
  if (payload.props.steps && payload.props.steps.length !== payload.props.totalSteps) {
    issues.push({ path: "$.props.steps", message: "steps array length must equal totalSteps." });
  }
  return issues;
};

// ----------- Layout schemas -----------

const spacingEnum = ["xs", "sm", "md", "lg", "xl"] as const;

const stackPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["stack"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      properties: {
        spacing: { type: "string" as const, enum: [...spacingEnum], optional: true },
      },
    },
  },
};

const rowPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["row"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      properties: {
        spacing: { type: "string" as const, enum: [...spacingEnum], optional: true },
        align: { type: "string" as const, enum: ["start", "center", "end", "stretch"], optional: true },
      },
    },
  },
};

const sectionPayloadSchema = {
  type: "object" as const,
  additionalProperties: false,
  required: ["component", "props"],
  properties: {
    component: { type: "string" as const, enum: ["section"] },
    props: {
      type: "object" as const,
      additionalProperties: false,
      properties: {
        title: stringSchema(true),
        description: stringSchema(true),
        collapsible: booleanSchema(true),
      },
    },
  },
};

const validateFormPayload = (payload: TWidgetFormPayload): TWidgetValidationIssue[] => {
  const issues = [] as TWidgetValidationIssue[];
  const fieldNames = payload.props.fields.map((field) => field.name);

  if (new Set(fieldNames).size !== fieldNames.length) {
    issues.push({
      path: "$.props.fields",
      message: "Form field names must be unique.",
    });
  }

  payload.props.fields.forEach((field, index) => {
    const optionRequired = field.type === "select" || field.type === "radio";
    if (optionRequired && (!field.options || field.options.length === 0)) {
      issues.push({
        path: `$.props.fields[${index}].options`,
        message: `${field.type} fields require at least one option.`,
      });
    }
  });

  return issues;
};

const validateButtonGroupPayload = (payload: TWidgetButtonGroupPayload): TWidgetValidationIssue[] => {
  const values = payload.props.buttons.map((button) => button.value);
  if (new Set(values).size !== values.length) {
    return [{ path: "$.props.buttons", message: "Button values must be unique." }];
  }
  return [];
};

const validateCardListPayload = (payload: TWidgetCardListPayload): TWidgetValidationIssue[] => {
  const ids = payload.props.cards.map((card) => card.id);
  if (new Set(ids).size !== ids.length) {
    return [{ path: "$.props.cards", message: "Card ids must be unique." }];
  }
  return [];
};

const validateDatePickerPayload = (payload: TWidgetDatePickerPayload): TWidgetValidationIssue[] => {
  if (payload.props.defaultValue && payload.props.mode === "time") {
    const isValidTime = /^\d{2}:\d{2}$/.test(payload.props.defaultValue);
    if (!isValidTime) {
      return [
        {
          path: "$.props.defaultValue",
          message: 'Time defaults must use the "HH:MM" format.',
        },
      ];
    }
  }

  return [];
};

export const defaultWidgetComponentDefinitions: readonly TRegisteredWidgetComponent[] = [
  {
    type: "form",
    version: "1",
    status: "active",
    description: "Multi-field form composition with built-in validation.",
    schema: formPayloadSchema,
    validatePayload: (payload) => validateFormPayload(payload as TWidgetFormPayload),
  },
  {
    type: "button_group",
    version: "1",
    status: "active",
    description: "Short-choice button group composition.",
    schema: buttonGroupPayloadSchema,
    validatePayload: (payload) => validateButtonGroupPayload(payload as TWidgetButtonGroupPayload),
  },
  {
    type: "card_list",
    version: "1",
    status: "active",
    description: "Selectable card-list composition for structured choices.",
    schema: cardListPayloadSchema,
    validatePayload: (payload) => validateCardListPayload(payload as TWidgetCardListPayload),
  },
  {
    type: "date_picker",
    version: "1",
    status: "active",
    description: "Date, time, or datetime composition.",
    schema: datePickerPayloadSchema,
    validatePayload: (payload) => validateDatePickerPayload(payload as TWidgetDatePickerPayload),
  },
  {
    type: "alert",
    version: "1",
    status: "active",
    description: "Existing alert primitive exposed through the widget registry.",
    schema: alertPayloadSchema,
  },
  {
    type: "text",
    version: "1",
    status: "active",
    description: "Rich text or markdown display block.",
    schema: textPayloadSchema,
  },
  {
    type: "image",
    version: "1",
    status: "active",
    description: "Image display with optional caption.",
    schema: imagePayloadSchema,
  },
  {
    type: "progress",
    version: "1",
    status: "active",
    description: "Step progress indicator for multi-step flows.",
    schema: progressPayloadSchema,
    validatePayload: (payload) => validateProgressPayload(payload as { props: { currentStep: number; totalSteps: number; steps?: TWidgetProgressStep[] } }),
  },
  {
    type: "table",
    version: "1",
    status: "active",
    description: "Data table with columns and rows.",
    schema: tablePayloadSchema,
  },
  {
    type: "divider",
    version: "1",
    status: "active",
    description: "Visual separator with optional label.",
    schema: dividerPayloadSchema,
  },
  {
    type: "stack",
    version: "1",
    status: "active",
    description: "Vertical layout — stacks children top to bottom.",
    schema: stackPayloadSchema,
  },
  {
    type: "row",
    version: "1",
    status: "active",
    description: "Horizontal layout — places children side by side.",
    schema: rowPayloadSchema,
  },
  {
    type: "section",
    version: "1",
    status: "active",
    description: "Grouped content with optional title/description.",
    schema: sectionPayloadSchema,
  },
];

export const registerDefaultWidgetComponents = (): void => {
  registerWidgetComponents(defaultWidgetComponentDefinitions);
};
