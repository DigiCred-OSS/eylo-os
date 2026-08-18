export {
  clearWidgetComponentRegistry,
  getActiveWidgetComponents,
  getRegisteredWidgetComponent,
  getRegisteredWidgetComponents,
  getWidgetComponentSchema,
  registerWidgetComponent,
  registerWidgetComponents,
  validateCompoundWidgetPayload,
  validateWidgetComponentDefinition,
  validateWidgetPayload,
} from "./service";
export {
  defaultWidgetComponentDefinitions,
  registerDefaultWidgetComponents,
} from "./catalog";

export type {
  TCompoundWidgetNode,
  TCompoundWidgetPayload,
  TRegisteredWidgetComponent,
  TWidgetComponentStatus,
  TWidgetComponentType,
  TWidgetInteraction,
  TWidgetPayloadEnvelope,
  TWidgetSchema,
  TWidgetValidationIssue,
  TWidgetValidationResult,
} from "./types";

export { isCompoundWidgetPayload } from "./types";
