import type { ComponentChildren } from "preact";
import { useState, type FC } from "preact/compat";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Stack,
} from "../../design-system";
import type { TWidgetSectionProps } from "./types";

type WidgetSectionRendererProps = {
  props: TWidgetSectionProps;
  children: ComponentChildren;
};

export const WidgetSection: FC<WidgetSectionRendererProps> = ({ props, children }) => {
  const canCollapse = props.collapsible && !!props.title;
  const [isCollapsed, setIsCollapsed] = useState(false);
  const hasHeader = props.title || props.description;

  return (
    <Card border shadow="sm">
      {hasHeader ? (
        <CardHeader>
          <Stack spacing="xs" direction="vertical">
            {props.title ? (
              <CardTitle
                style={canCollapse ? { cursor: "pointer", userSelect: "none" } : undefined}
                onClick={canCollapse ? () => setIsCollapsed((c) => !c) : undefined}
              >
                {canCollapse ? (isCollapsed ? "▸ " : "▾ ") : ""}
                {props.title}
              </CardTitle>
            ) : null}
            {props.description ? <CardDescription>{props.description}</CardDescription> : null}
          </Stack>
        </CardHeader>
      ) : null}
      {!isCollapsed ? <CardContent>{children}</CardContent> : null}
    </Card>
  );
};
