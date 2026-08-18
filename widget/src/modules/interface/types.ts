export type TWidgetComponentType = string;

export type TWidgetComponentStatus = "active" | "deferred";

export type TWidgetSchema =
  | {
      type: "string";
      enum?: readonly string[];
      minLength?: number;
      maxLength?: number;
      pattern?: string;
      optional?: boolean;
    }
  | {
      type: "number";
      min?: number;
      max?: number;
      optional?: boolean;
    }
  | {
      type: "boolean";
      optional?: boolean;
    }
  | {
      type: "any";
      optional?: boolean;
    }
  | {
      type: "array";
      items: TWidgetSchema;
      minItems?: number;
      maxItems?: number;
      optional?: boolean;
    }
  | {
      type: "object";
      properties: Record<string, TWidgetSchema>;
      required?: readonly string[];
      additionalProperties?: boolean;
      optional?: boolean;
    };

export type TWidgetValidationIssue = {
  path: string;
  message: string;
};

export type TWidgetValidationResult<T = unknown> =
  | {
      ok: true;
      value: T;
      issues: [];
    }
  | {
      ok: false;
      issues: TWidgetValidationIssue[];
    };

export type TWidgetPayloadEnvelope<
  TType extends TWidgetComponentType = TWidgetComponentType,
  TProps = unknown,
> = {
  component: TType;
  props: TProps;
};

export type TCompoundWidgetNode = {
  id: string;
  component: TWidgetComponentType;
  props: Record<string, unknown>;
  children?: string[];
};

export type TCompoundWidgetPayload = {
  components: TCompoundWidgetNode[];
  root: string;
};

/**
 * Detect whether a widget message payload is compound (adjacency list)
 * or single (component + props).
 */
export const isCompoundWidgetPayload = (
  payload: unknown
): payload is TCompoundWidgetPayload => {
  if (typeof payload !== "object" || payload === null) return false;
  return "components" in payload && "root" in payload;
};

export type TRegisteredWidgetComponent = {
  type: TWidgetComponentType;
  version: string;
  status: TWidgetComponentStatus;
  schema: TWidgetSchema;
  description?: string;
  validatePayload?: (payload: TWidgetPayloadEnvelope) => TWidgetValidationIssue[];
};

export type TWidgetInteraction = {
  component: TWidgetComponentType;
  action: string;
  data: Record<string, unknown>;
};
