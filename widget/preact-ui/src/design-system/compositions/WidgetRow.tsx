import type { ComponentChildren } from "preact";
import type { FC } from "preact/compat";
import { Flex } from "../components/Flex";
import type { TWidgetRowProps } from "./types";

type WidgetRowRendererProps = {
  props: TWidgetRowProps;
  children: ComponentChildren;
};

export const WidgetRow: FC<WidgetRowRendererProps> = ({ props, children }) => {
  return (
    <Flex gap={props.spacing ?? "md"} direction="row" align={props.align ?? "stretch"} wrap="wrap">
      {children}
    </Flex>
  );
};
