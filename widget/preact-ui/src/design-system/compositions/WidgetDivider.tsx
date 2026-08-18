import type { ComponentChildren } from "preact";
import type { FC } from "preact/compat";
import type { TCompoundWidgetNode } from "@eylo";
import { Separator } from "../components/Separator";
import { Text } from "../components/Typography";

type WidgetDividerRendererProps = {
  node: TCompoundWidgetNode;
  children: ComponentChildren;
};

export const WidgetDivider: FC<WidgetDividerRendererProps> = ({ node }) => {
  const label = (node.props as { label?: string }).label;

  if (label) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", width: "100%" }}>
        <Separator />
        <Text size="small" variant="muted">
          {label}
        </Text>
        <Separator />
      </div>
    );
  }

  return <Separator />;
};
