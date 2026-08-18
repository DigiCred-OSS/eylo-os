import type { FC } from "preact/compat";
import type { WidgetRendererProps } from "../../components/DynamicWidget/registry";
import type { TWidgetImagePayload } from "./types";
import { Text } from "../components/Typography";
import { Stack } from "../components/Stack";

export const WidgetImage: FC<WidgetRendererProps<TWidgetImagePayload>> = ({ payload }) => {
  const { src, alt, caption, width, height } = payload.props;

  return (
    <Stack spacing="xs" direction="vertical">
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        style={{
          maxWidth: "100%",
          height: "auto",
          borderRadius: "var(--radius)",
          display: "block",
        }}
        loading="lazy"
      />
      {caption ? (
        <Text variant="muted" size="small">
          {caption}
        </Text>
      ) : null}
    </Stack>
  );
};
