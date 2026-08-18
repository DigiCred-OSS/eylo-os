import { defaultWidgetComponentDefinitions, registerDefaultWidgetComponents } from "@eylo";

export const widgetComponentDefinitions = defaultWidgetComponentDefinitions;

export const registerDynamicWidgetComponents = (): void => {
  registerDefaultWidgetComponents();
};
