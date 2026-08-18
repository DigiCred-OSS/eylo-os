import type { TWidgetPayloadEnvelope } from "@eylo";

export type TWidgetButtonVariant =
  | "primary"
  | "secondary"
  | "destructive"
  | "ghost"
  | "outline"
  | "link";

export type TWidgetFormFieldType =
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

export type TWidgetFieldValidation = {
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  pattern?: string;
  message?: string;
  minDate?: string;
  maxDate?: string;
};

export type TWidgetOption = {
  value: string;
  label: string;
  description?: string;
};

export type TWidgetFormField = {
  type: TWidgetFormFieldType;
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  defaultValue?: unknown;
  options?: TWidgetOption[];
  validation?: TWidgetFieldValidation;
};

export type TWidgetFormProps = {
  title: string;
  description?: string;
  fields: TWidgetFormField[];
  submitLabel?: string;
  cancelLabel?: string;
};

export type TWidgetButtonGroupButton = {
  value: string;
  label: string;
  variant?: TWidgetButtonVariant;
  icon?: string;
};

export type TWidgetButtonGroupProps = {
  question?: string;
  buttons: TWidgetButtonGroupButton[];
  layout?: "horizontal" | "vertical";
};

export type TWidgetCardListCard = {
  id: string;
  title: string;
  description?: string;
  image?: string;
  price?: string;
  badge?: string;
  features?: string[];
};

export type TWidgetCardListProps = {
  title?: string;
  description?: string;
  selectionMode?: "single" | "multiple";
  cards: TWidgetCardListCard[];
  submitLabel?: string;
};

export type TWidgetDatePickerProps = {
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

export type TWidgetAlertProps = {
  title?: string;
  message: string;
  severity?: "info" | "success" | "warning" | "error";
  dismissible?: boolean;
};

export type TWidgetFormPayload = TWidgetPayloadEnvelope<"form", TWidgetFormProps>;

export type TWidgetButtonGroupPayload = TWidgetPayloadEnvelope<
  "button_group",
  TWidgetButtonGroupProps
>;

export type TWidgetCardListPayload = TWidgetPayloadEnvelope<"card_list", TWidgetCardListProps>;

export type TWidgetDatePickerPayload = TWidgetPayloadEnvelope<
  "date_picker",
  TWidgetDatePickerProps
>;

export type TWidgetAlertPayload = TWidgetPayloadEnvelope<"alert", TWidgetAlertProps>;

// New Tier-1 content components (display-only)

export type TWidgetTextProps = {
  content: string;
  variant?: "body" | "heading" | "caption" | "code";
};

export type TWidgetImageProps = {
  src: string;
  alt: string;
  caption?: string;
  width?: number;
  height?: number;
};

export type TWidgetProgressStep = {
  label: string;
  status: "pending" | "active" | "completed";
};

export type TWidgetProgressProps = {
  currentStep: number;
  totalSteps: number;
  label?: string;
  steps?: TWidgetProgressStep[];
};

export type TWidgetTableColumn = {
  key: string;
  label: string;
  align?: "left" | "center" | "right";
};

export type TWidgetTableProps = {
  columns: TWidgetTableColumn[];
  rows: Record<string, unknown>[];
  caption?: string;
};

export type TWidgetTextPayload = TWidgetPayloadEnvelope<"text", TWidgetTextProps>;
export type TWidgetImagePayload = TWidgetPayloadEnvelope<"image", TWidgetImageProps>;
export type TWidgetProgressPayload = TWidgetPayloadEnvelope<"progress", TWidgetProgressProps>;
export type TWidgetTablePayload = TWidgetPayloadEnvelope<"table", TWidgetTableProps>;

// Layout component payloads (structural only — no submissions)

export type TWidgetDividerProps = {
  label?: string;
};

export type TWidgetStackProps = {
  spacing?: "xs" | "sm" | "md" | "lg" | "xl";
};

export type TWidgetRowProps = {
  spacing?: "xs" | "sm" | "md" | "lg" | "xl";
  align?: "start" | "center" | "end" | "stretch";
};

export type TWidgetSectionProps = {
  title?: string;
  description?: string;
  collapsible?: boolean;
};

export type TWidgetStackPayload = TWidgetPayloadEnvelope<"stack", TWidgetStackProps>;
export type TWidgetRowPayload = TWidgetPayloadEnvelope<"row", TWidgetRowProps>;
export type TWidgetSectionPayload = TWidgetPayloadEnvelope<"section", TWidgetSectionProps>;
export type TWidgetDividerPayload = TWidgetPayloadEnvelope<"divider", TWidgetDividerProps>;

export type TDynamicWidgetPayload =
  | TWidgetFormPayload
  | TWidgetButtonGroupPayload
  | TWidgetCardListPayload
  | TWidgetDatePickerPayload
  | TWidgetAlertPayload
  | TWidgetTextPayload
  | TWidgetImagePayload
  | TWidgetProgressPayload
  | TWidgetTablePayload
  | TWidgetStackPayload
  | TWidgetRowPayload
  | TWidgetSectionPayload
  | TWidgetDividerPayload;
