import type { ComponentChildren, ComponentType } from "preact";
import type { TWidgetInteraction, TWidgetResponseData, TCompoundWidgetNode } from "@eylo";
import {
  WidgetButtonGroup,
  WidgetCardList,
  WidgetDatePicker,
  WidgetDivider,
  WidgetForm,
  WidgetImage,
  WidgetProgress,
  WidgetRow,
  WidgetSection,
  WidgetStack,
  WidgetTable,
  WidgetText,
} from "../../design-system/compositions";
import { Alert, AlertDescription, AlertTitle } from "../../design-system";
import type {
  TDynamicWidgetPayload,
  TWidgetAlertPayload,
  TWidgetButtonGroupPayload,
  TWidgetCardListPayload,
  TWidgetDatePickerPayload,
  TWidgetFormPayload,
  TWidgetImagePayload,
  TWidgetProgressPayload,
  TWidgetRowProps,
  TWidgetSectionProps,
  TWidgetStackProps,
  TWidgetTablePayload,
  TWidgetTextPayload,
} from "../../design-system/compositions/types";

export type WidgetRendererProps<TPayload extends TDynamicWidgetPayload = TDynamicWidgetPayload> = {
  payload: TPayload;
  onInteraction?: (interaction: TWidgetInteraction) => void;
  isReadOnly?: boolean;
  submission?: TWidgetResponseData | null;
};

type WidgetRendererMap = {
  form: ComponentType<WidgetRendererProps<TWidgetFormPayload>>;
  button_group: ComponentType<WidgetRendererProps<TWidgetButtonGroupPayload>>;
  card_list: ComponentType<WidgetRendererProps<TWidgetCardListPayload>>;
  date_picker: ComponentType<WidgetRendererProps<TWidgetDatePickerPayload>>;
  alert: ComponentType<WidgetRendererProps<TWidgetAlertPayload>>;
  text: ComponentType<WidgetRendererProps<TWidgetTextPayload>>;
  image: ComponentType<WidgetRendererProps<TWidgetImagePayload>>;
  progress: ComponentType<WidgetRendererProps<TWidgetProgressPayload>>;
  table: ComponentType<WidgetRendererProps<TWidgetTablePayload>>;
};

const WidgetAlertRenderer: WidgetRendererMap["alert"] = ({ payload }) => {
  const severityToVariant = {
    info: "info",
    success: "success",
    warning: "warning",
    error: "destructive",
  } as const;

  const variant = severityToVariant[payload.props.severity || "info"];

  return (
    <Alert variant={variant}>
      {payload.props.title ? <AlertTitle>{payload.props.title}</AlertTitle> : null}
      <AlertDescription>{payload.props.message}</AlertDescription>
    </Alert>
  );
};

const widgetRendererMap: WidgetRendererMap = {
  form: WidgetForm,
  button_group: WidgetButtonGroup,
  card_list: WidgetCardList,
  date_picker: WidgetDatePicker,
  alert: WidgetAlertRenderer,
  text: WidgetText,
  image: WidgetImage,
  progress: WidgetProgress,
  table: WidgetTable,
};

export const getWidgetRenderer = (type: string): ComponentType<WidgetRendererProps> | undefined => {
  return widgetRendererMap[type as keyof WidgetRendererMap] as
    | ComponentType<WidgetRendererProps>
    | undefined;
};

// ---------------------------------------------------------------------------
// Layout component wrappers (accept children from compound tree resolver)
// ---------------------------------------------------------------------------

type LayoutRendererProps = {
  node: TCompoundWidgetNode;
  children: ComponentChildren;
};

const layoutRendererMap: Record<string, ComponentType<LayoutRendererProps>> = {
  stack: ({ node, children }) => (
    <WidgetStack props={node.props as TWidgetStackProps}>{children}</WidgetStack>
  ),
  row: ({ node, children }) => (
    <WidgetRow props={node.props as TWidgetRowProps}>{children}</WidgetRow>
  ),
  section: ({ node, children }) => (
    <WidgetSection props={node.props as TWidgetSectionProps}>{children}</WidgetSection>
  ),
  divider: ({ node, children }) => <WidgetDivider node={node}>{children}</WidgetDivider>,
};

export const isLayoutComponent = (type: string): boolean => type in layoutRendererMap;

export const getLayoutRenderer = (type: string): ComponentType<LayoutRendererProps> | undefined => {
  return layoutRendererMap[type];
};
