import type { ComponentChildren } from "preact";
import type { FC } from "preact/compat";
import { Stack } from "../components/Stack";
import type { TWidgetStackProps } from "./types";

type WidgetStackRendererProps = {
  props: TWidgetStackProps;
  children: ComponentChildren;
};

export const WidgetStack: FC<WidgetStackRendererProps> = ({ props, children }) => {
  return (
    <Stack spacing={props.spacing ?? "md"} direction="vertical">
      {children}
    </Stack>
  );
};
