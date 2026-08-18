import { useState, type FC } from "preact/compat";
import type { TWidgetInteraction, TWidgetResponseData } from "@eylo";
import { Button, Card, CardContent, CardHeader, CardTitle, Flex, Stack, Text } from "../index";
import type { TWidgetButtonGroupPayload } from "./types";

type WidgetButtonGroupProps = {
  payload: TWidgetButtonGroupPayload;
  onInteraction?: (interaction: TWidgetInteraction) => void;
  isReadOnly?: boolean;
  submission?: TWidgetResponseData | null;
};

const toButtonVariant = (variant?: string) => {
  if (variant === "primary") return "default" as const;
  if (variant === "secondary") return "secondary" as const;
  if (variant === "destructive") return "destructive" as const;
  if (variant === "ghost") return "ghost" as const;
  if (variant === "outline") return "outline" as const;
  if (variant === "link") return "link" as const;
  return "default" as const;
};

export const WidgetButtonGroup: FC<WidgetButtonGroupProps> = ({
  payload,
  onInteraction,
  isReadOnly = false,
  submission = null,
}) => {
  const { props } = payload;
  const [isSubmitted, setIsSubmitted] = useState(Boolean(submission));
  const effectiveReadOnly = isReadOnly || isSubmitted;
  const isVertical = props.layout === "vertical";
  const selectedLabel =
    typeof submission?.data.label === "string"
      ? submission.data.label
      : typeof submission?.data.value === "string"
        ? submission.data.value
        : null;

  return (
    <Card border shadow="sm">
      {props.question ? (
        <CardHeader>
          <CardTitle>{props.question}</CardTitle>
        </CardHeader>
      ) : null}
      <CardContent>
        <Flex direction={isVertical ? "column" : "row"} wrap="wrap" gap="sm">
          {props.buttons.map((button) => (
            <Button
              key={button.value}
              variant={toButtonVariant(button.variant)}
              onClick={() => {
                setIsSubmitted(true);
                onInteraction?.({
                  component: "button_group",
                  action: "select",
                  data: { value: button.value, label: button.label },
                });
              }}
              disabled={effectiveReadOnly}
            >
              {button.label}
            </Button>
          ))}
        </Flex>
        {effectiveReadOnly ? (
          <Stack spacing="xs">
            <Text size="small" variant="muted">
              This button group is now read-only.
            </Text>
            {selectedLabel ? (
              <Text size="small" variant="muted">
                Selected: {selectedLabel}
              </Text>
            ) : null}
          </Stack>
        ) : null}
      </CardContent>
    </Card>
  );
};
