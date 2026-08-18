import type { FC } from "preact/compat";
import type { WidgetRendererProps } from "../../components/DynamicWidget/registry";
import type { TWidgetTextPayload } from "./types";
import { Code, Heading, Text } from "../components/Typography";

export const WidgetText: FC<WidgetRendererProps<TWidgetTextPayload>> = ({ payload }) => {
  const { content, variant = "body" } = payload.props;

  switch (variant) {
    case "heading":
      return <Heading as="h3">{content}</Heading>;
    case "caption":
      return (
        <Text variant="muted" size="small">
          {content}
        </Text>
      );
    case "code":
      return <Code>{content}</Code>;
    default:
      return <Text>{content}</Text>;
  }
};
